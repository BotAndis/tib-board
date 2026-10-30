"""Upload the local 'Übersicht Main Datein' tree to Seafile: only files missing there or with a different size.

Reuses the Seafile-MCP login. Safe to re-run (no '(1)' duplicates, changed files replace the server copy,
the old version stays in Seafile's history). Deletes nothing on the server.
Run: uv run --no-project --python 3.12 --with mcp==1.27.2 python sync_seafile.py
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, "D:/Claude_Workspaces/CX-NEA/Seafile-MCP")
import server as sf  # noqa: E402

LOCAL = Path("D:/UNI/Bachelor/Übersicht Main Datein")
LIB, REMOTE = "Neuer Start", "/Bachelor Kempe/Übersicht Main Datein"

repo = sf._repo(LIB)
remote = {f"{f['parent_dir'].rstrip('/')}/{f['name']}": f["size"]
          for f in sf.api("GET", f"/api2/repos/{repo}/dir/", params={"p": REMOTE, "t": "f", "recursive": 1})}
todo = [p for p in sorted(LOCAL.rglob("*")) if p.is_file()
        and remote.get(f"{REMOTE}/{p.relative_to(LOCAL).as_posix()}") != p.stat().st_size]
print(f"{len(todo)} of {sum(1 for p in LOCAL.rglob('*') if p.is_file())} files to upload", flush=True)

for i, p in enumerate(todo, 1):
    parent = f"{REMOTE}/{p.parent.relative_to(LOCAL).as_posix()}".removesuffix("/.")
    url = sf.api("GET", f"/api2/repos/{repo}/upload-link/", params={"p": REMOTE})
    with open(p, "rb") as fh:
        r = httpx.post(url, params={"ret-json": 1}, files={"file": (p.name, fh)}, timeout=None,
                       data={"parent_dir": REMOTE, "relative_path": parent[len(REMOTE):].strip("/"), "replace": "1"},
                       headers={"Authorization": f"Token {sf._token()}"})
    r.raise_for_status()
    print(f"[{i}/{len(todo)}] {parent}/{p.name}", flush=True)
print("done")
