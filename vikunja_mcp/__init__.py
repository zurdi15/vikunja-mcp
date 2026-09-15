"""vikunja-mcp — servidor MCP (stdio) mínimo para una instancia de Vikunja.

Configuración por variables de entorno (las pone el .mcp.json de cada repo):

  VIKUNJA_URL      https://vikunja.example.net   (obligatoria)
  VIKUNJA_TOKEN    tk_…  API token de Vikunja     (obligatoria; NUNCA en el repo:
                   el .mcp.json la referencia como ${VIKUNJA_TOKEN})
  VIKUNJA_PROJECT  proyecto por defecto (id o título) para las herramientas que
                   aceptan `project` opcional

Las descripciones de Vikunja son HTML: se devuelven como texto plano y las que
se escriben se envuelven en <p>.
"""

from __future__ import annotations

import html
import os
import re
from typing import Any

import httpx

try:  # mcp 2.x renombró FastMCP → MCPServer; 1.x sigue con FastMCP
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server

mcp = _Server(
    "vikunja",
    instructions=(
        "Tableros de tareas del usuario en Vikunja. Lee el proyecto con list_tasks antes de "
        "ponerte a trabajar, marca una tarea hecha (update_task done=true) solo cuando el "
        "cambio esté terminado y empujado como espera el repo, y deja un add_comment con el "
        "commit o versión que la cerró. Nunca pidas la URL ni el token: ya están configurados."
    ),
)


def _env(name: str, required: bool = True) -> str | None:
    value = os.environ.get(name, "").strip()
    if not value and required:
        raise RuntimeError(
            f"vikunja-mcp: falta la variable {name}. Defínela en el entorno de la máquina "
            "(el .mcp.json del repo la referencia como ${" + name + "})."
        )
    return value or None


def _client() -> httpx.Client:
    url = _env("VIKUNJA_URL").rstrip("/")
    token = _env("VIKUNJA_TOKEN")
    return httpx.Client(
        base_url=f"{url}/api/v1",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20,
    )


def _call(method: str, path: str, **kwargs) -> Any:
    with _client() as client:
        resp = client.request(method, path, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"Vikunja {resp.status_code} en {method} {path}: {resp.text[:300]}")
    return resp.json() if resp.content else None


def strip_html(text: str | None) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", text or "")
    text = re.sub(r"<li>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def to_html(text: str) -> str:
    paragraphs = [html.escape(p.strip()) for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def _task_view(t: dict) -> dict:
    """Proyección compacta de una tarea: lo que un agente necesita, sin ruido."""
    due = t.get("due_date")
    return {
        "id": t["id"],
        "title": t.get("title"),
        "done": bool(t.get("done")),
        "description": strip_html(t.get("description")),
        "project_id": t.get("project_id"),
        "labels": [l["title"] for l in (t.get("labels") or [])],
        "priority": t.get("priority") or 0,
        "due_date": None if not due or str(due).startswith("0001") else str(due)[:10],
        "created": str(t.get("created", ""))[:10],
        "updated": str(t.get("updated", ""))[:10],
    }


def _resolve_project(ref: str | None) -> dict:
    ref = (ref or _env("VIKUNJA_PROJECT", required=False) or "").strip()
    if not ref:
        raise RuntimeError(
            "vikunja-mcp: indica `project` (id o título) o define VIKUNJA_PROJECT en el .mcp.json"
        )
    projects = _call("GET", "/projects", params={"per_page": 100}) or []
    for p in projects:
        if ref.isdigit() and p["id"] == int(ref):
            return p
    for p in projects:
        if p["title"].lower() == ref.lower():
            return p
    names = ", ".join(f"{p['id']}={p['title']}" for p in projects)
    raise RuntimeError(f"vikunja-mcp: proyecto '{ref}' no encontrado. Disponibles: {names}")


# ---- herramientas ----


@mcp.tool()
def list_projects() -> list[dict]:
    """Lista los proyectos de Vikunja (id, título, archivado)."""
    projects = _call("GET", "/projects", params={"per_page": 100}) or []
    return [
        {"id": p["id"], "title": p["title"], "archived": bool(p.get("is_archived"))}
        for p in projects
    ]


@mcp.tool()
def list_tasks(project: str | None = None, include_done: bool = False) -> dict:
    """Tareas de un proyecto (id o título; sin `project` usa VIKUNJA_PROJECT).
    Por defecto solo las pendientes, ordenadas por id."""
    proj = _resolve_project(project)
    tasks = _call("GET", f"/projects/{proj['id']}/tasks", params={"per_page": 200}) or []
    if not include_done:
        tasks = [t for t in tasks if not t.get("done")]
    tasks.sort(key=lambda t: (bool(t.get("done")), t["id"]))
    return {"project": {"id": proj["id"], "title": proj["title"]}, "tasks": [_task_view(t) for t in tasks]}


@mcp.tool()
def get_task(task_id: int) -> dict:
    """Una tarea con su descripción completa (texto plano)."""
    return _task_view(_call("GET", f"/tasks/{task_id}"))


@mcp.tool()
def create_task(title: str, description: str = "", project: str | None = None) -> dict:
    """Crea una tarea en un proyecto (sin `project` usa VIKUNJA_PROJECT). La
    descripción es texto plano; los párrafos se separan con línea en blanco."""
    proj = _resolve_project(project)
    body: dict[str, Any] = {"title": title}
    if description:
        body["description"] = to_html(description)
    return _task_view(_call("PUT", f"/projects/{proj['id']}/tasks", json=body))


@mcp.tool()
def update_task(
    task_id: int,
    done: bool | None = None,
    title: str | None = None,
    description: str | None = None,
) -> dict:
    """Actualiza una tarea: `done=true` la cierra (false la reabre); título y
    descripción opcionales. Solo se envían los campos indicados."""
    current = _call("GET", f"/tasks/{task_id}")
    body: dict[str, Any] = {"title": current.get("title")}  # Vikunja exige title en el POST
    if done is not None:
        body["done"] = done
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = to_html(description)
    return _task_view(_call("POST", f"/tasks/{task_id}", json=body))


@mcp.tool()
def add_comment(task_id: int, text: str) -> dict:
    """Añade un comentario a una tarea (p. ej. el commit o la versión que la cerró)."""
    c = _call("PUT", f"/tasks/{task_id}/comments", json={"comment": to_html(text)})
    return {"id": c["id"], "task_id": task_id, "comment": strip_html(c.get("comment"))}


@mcp.tool()
def list_comments(task_id: int) -> list[dict]:
    """Comentarios de una tarea, en orden."""
    comments = _call("GET", f"/tasks/{task_id}/comments") or []
    return [
        {
            "id": c["id"],
            "author": (c.get("author") or {}).get("username"),
            "created": str(c.get("created", ""))[:16],
            "comment": strip_html(c.get("comment")),
        }
        for c in comments
    ]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
