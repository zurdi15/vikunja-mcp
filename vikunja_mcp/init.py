"""vikunja-mcp-init — deja el servidor configurado en el repo actual.

    uvx --from git+https://github.com/zurdi15/vikunja-mcp vikunja-mcp-init "Mi proyecto"

Escribe (o completa) el `.mcp.json` del directorio actual con la entrada `vikunja`:
la URL y el proyecto por defecto van en claro; el token queda como `${VIKUNJA_TOKEN}`
para que Claude Code lo lea del entorno de cada máquina. Nunca escribe el token.

Con `--local` no toca el repo: registra la misma entrada solo para ti en este proyecto
(`claude mcp add-json --scope local`, guardado en ~/.claude.json).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = "git+https://github.com/zurdi15/vikunja-mcp"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vikunja-mcp-init", description=__doc__.split("\n\n")[0])
    parser.add_argument("project", nargs="?", help="proyecto por defecto (título o id); por defecto, el nombre de la carpeta")
    parser.add_argument("--url", default=os.environ.get("VIKUNJA_URL"), help="URL de Vikunja (o VIKUNJA_URL del entorno)")
    parser.add_argument("--ref", default="", help="revisión del servidor a fijar, p. ej. v0.1.0 (por defecto, main)")
    parser.add_argument("--path", default=".mcp.json", help="fichero a escribir (por defecto ./.mcp.json)")
    parser.add_argument(
        "--local",
        action="store_true",
        help="registrar el servidor solo para ti en este proyecto (claude mcp add-json --scope local) sin escribir .mcp.json",
    )
    args = parser.parse_args(argv)

    if not args.url:
        sys.exit("vikunja-mcp-init: indica --url o define VIKUNJA_URL en el entorno")
    project = args.project or Path.cwd().name
    source = f"{SOURCE}@{args.ref}" if args.ref else SOURCE

    entry = {
        "command": "uvx",
        "args": ["--from", source, "vikunja-mcp"],
        "env": {
            "VIKUNJA_URL": args.url.rstrip("/"),
            "VIKUNJA_PROJECT": project,
            "VIKUNJA_TOKEN": "${VIKUNJA_TOKEN}",
        },
    }

    if args.local:
        register_local(entry)
        print(f"scope local: servidor 'vikunja' -> {args.url} (proyecto por defecto: {project})")
    else:
        path = Path(args.path)
        config: dict = {}
        if path.exists():
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                sys.exit(f"vikunja-mcp-init: {path} no es JSON válido: {exc}")
        config.setdefault("mcpServers", {})["vikunja"] = entry
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{path}: servidor 'vikunja' -> {args.url} (proyecto por defecto: {project})")
    if not os.environ.get("VIKUNJA_TOKEN"):
        print(
            "aviso: VIKUNJA_TOKEN no está en el entorno de esta máquina; sin ella el servidor no arranca "
            "(ver README: export VIKUNJA_TOKEN=... o [Environment]::SetEnvironmentVariable en Windows)",
            file=sys.stderr,
        )


def register_local(entry: dict) -> None:
    """Registra `entry` como servidor `vikunja` en el scope local de Claude Code (re-ejecutable)."""
    claude = shutil.which("claude")
    if not claude:
        sys.exit("vikunja-mcp-init: --local necesita el CLI `claude` en el PATH")
    # add-json falla si el nombre ya existe en ese scope; quitarlo antes lo hace idempotente.
    subprocess.run([claude, "mcp", "remove", "vikunja", "--scope", "local"], capture_output=True)
    result = subprocess.run(
        [claude, "mcp", "add-json", "vikunja", json.dumps(entry), "--scope", "local"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"vikunja-mcp-init: error en claude mcp add-json: {result.stderr.strip() or result.stdout.strip()}")


if __name__ == "__main__":
    main()
