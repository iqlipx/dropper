#!/usr/bin/env python3

import os
import sys
import argparse
import pathlib
import base64
from datetime import datetime
from functools import wraps
from flask import Flask, request, send_from_directory, abort, Response, render_template_string, redirect, url_for, jsonify



# ---------------------------
# Args / root
# ---------------------------

parser = argparse.ArgumentParser(
    description="""
dropper.py - Simple file dropper server

Usage:
    python dropper.py [--dir PATH] [--host HOST] [--port PORT] [--no-auth]

Options:
    --dir      Root directory to serve (default: current working directory ".")
    --host     Host to bind the server (default: 127.0.0.1)
    --port     Port to run the server on (default: 8000)
    --no-auth  Disable authentication for this run

Authentication:
    By default, the server requires basic authentication. Set the environment variable:

        export DROP_AUTH="user:pass"   # Linux/macOS
        set DROP_AUTH=user:pass        # Windows CMD
        $env:DROP_AUTH="user:pass"    # Windows PowerShell

    Use --no-auth to temporarily disable authentication (not recommended on public networks).

Direct download shortcut:
    All files can be accessed via the /drop/<filename> path. This provides a convenient 
    way to download files without navigating through directories.

    Example:
        wget http://<ip-address>:<port>/drop/linpeas.sh
        curl -O http://<ip-address>:<port>/drop/winpeas.exe

Description:
    Dropper is a lightweight Flask-based server for sharing files over HTTP. 

    Features:
      - Browse directories and view files with metadata (size, modification time)
      - Search for files by name
      - Direct download shortcut via /drop/<filename>
      - authentication for secure access
      - Simple to set up and run on any host
""",
    formatter_class=argparse.RawDescriptionHelpFormatter
)

parser.add_argument("--dir", help="root directory to serve", default=".")
parser.add_argument("--host", help="bind host", default="127.0.0.1")
parser.add_argument("--port", help="port", default="8000")
parser.add_argument("--no-auth", action="store_true", help="disable authentication for this run")

args = parser.parse_args()


ROOT = pathlib.Path(args.dir).resolve()
if not ROOT.exists():
    print("Creating root:", ROOT)
    ROOT.mkdir(parents=True, exist_ok=True)

# ---------------------------
# Auth (mandatory unless --no-auth)
# ---------------------------
AUTH = None if args.no_auth else os.environ.get("DROP_AUTH")  # format user:pass

if not args.no_auth and not AUTH:
    print("\nERROR: DROP_AUTH environment variable is not set.")
    print("Please set a username and password to secure the server. Format: user:pass")
    print("\nExample:")
    print("  On Linux/macOS terminal:")
    print("    export DROP_AUTH=\"admin:mypassword\"")
    print("  On Windows CMD:")
    print("    set DROP_AUTH=admin:mypassword")
    print("  On Windows PowerShell:")
    print("    $env:DROP_AUTH=\"admin:mypassword\"\n")
    print("If you want to run the server without authentication, use the --no-auth flag.")
    sys.exit(1)

def check_auth_header(header):
    if not header:
        return False
    try:
        typ, creds = header.split(None, 1)
        if typ.lower() != "basic":
            return False
        decoded = base64.b64decode(creds).decode("utf-8")
        return decoded == AUTH
    except Exception:
        return False

def requires_auth(func):
    @wraps(func)
    def inner(*a, **kw):
        # Skip auth if AUTH is None
        if AUTH is None or check_auth_header(request.headers.get("Authorization")):
            return func(*a, **kw)
        return Response(
            "Authentication required",
            401,
            {"WWW-Authenticate": 'Basic realm="Dropper"'}
        )
    return inner

# ---------------------------
# Flask app
# ---------------------------
app = Flask(__name__, static_folder=None)

# ---------------------------
# Filesystem helpers
# ---------------------------
def human_size(n):
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def safe_resolve(rel_path: str) -> pathlib.Path:
    """
    Resolve a user-supplied relative path and ensure it's inside ROOT.
    Returns the resolved Path or raises abort(404) on invalid.
    """
    target = (ROOT / rel_path).resolve()
    try:
        target.relative_to(ROOT)
    except Exception:
        abort(404)
    return target

def list_dir(rel_path: str):
    """List directories & files for a relative path (non-recursive)."""
    p = safe_resolve(rel_path)
    if not p.exists() or not p.is_dir():
        abort(404)
    dirs = []
    files = []
    for child in sorted(p.iterdir()):
        if child.is_dir():
            dirs.append({
                "name": child.name,
                "relpath": str((pathlib.Path(rel_path) / child.name).as_posix()),
                "mtime": datetime.fromtimestamp(child.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        elif child.is_file():
            files.append({
                "name": child.name,
                "relpath": str((pathlib.Path(rel_path) / child.name).as_posix()),
                "size": human_size(child.stat().st_size),
                "mtime": datetime.fromtimestamp(child.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    return {"dirs": dirs, "files": files, "cwd": str(pathlib.Path(rel_path).as_posix())}

def build_index():  # flat index of files (useful for search)
    out = []
    for root, dirs, files in os.walk(ROOT):
        root_p = pathlib.Path(root)
        rel_root = root_p.relative_to(ROOT).as_posix()
        for f in files:
            fp = root_p / f
            out.append({
                "name": f,
                "relpath": (pathlib.Path(rel_root) / f).as_posix() if rel_root != "." else f,
                "size": human_size(fp.stat().st_size),
                "mtime": datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    return out

# ---------------------------
# UI templates
# ---------------------------
INDEX_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Dropper</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:18px;max-width:1100px}
 header{display:flex;justify-content:space-between;align-items:center}
 nav.breadcrumb{font-size:0.95rem;color:#555;font-weight: bold;}
 .grid{display:flex;gap:16px;flex-wrap:wrap;margin-top:18px}
 .card{border:1px solid #e6e6e6;padding:12px;border-radius:8px;min-width:220px;flex:1}
 a{color:#0a66c2;text-decoration:none}
 .file{margin:6px 0;font-size:0.95rem}
 .meta{font-size:0.85rem;color:#666}
 input.search{padding:8px;width:48%}
 button.btn{padding:6px 10px;border-radius:6px;border:1px solid #ccc;background:#fafafa}
 .small{font-size:0.85rem;color:#666}
 nav.breadcrumb a { color:#0a66c2; font-weight:bold; text-decoration:none; }
 nav.breadcrumb a:hover { text-decoration:underline; }
</style>
</head>
<body>
<header>
  <div>
    <h2>Dropper</h2>
    <div class="small">Root: <strong>{{ root }}</strong></div>
  </div>
  <div>
    <input id="q" class="search" placeholder="search filenames" />
    <button class="btn" onclick="refresh()">Refresh</button>
  </div>
</header>

<nav class="breadcrumb" id="breadcrumb"></nav>
<div id="content" class="grid"></div>

<footer style="margin-top:22px;color:#666;font-size:0.85rem">
  Tip: keep Dropper on localhost or behind a VPN. Don't expose to public internet.
</footer>

<script>
let cwd = "{{ start }}"; // initial path (may be "")

async function refresh(){
    await loadDir(cwd);
}

async function loadDir(path){
    const p = encodeURIComponent(path || ".");
    const resp = await fetch('/_ls?path=' + p);
    if(!resp.ok){
        document.getElementById('content').innerHTML = '<div>Error loading directory</div>';
        return;
    }
    const obj = await resp.json();
    cwd = obj.cwd === "." ? "" : obj.cwd;
    renderBreadcrumb(cwd);
    renderContent(obj);
}

function renderBreadcrumb(path){
    const bc = document.getElementById('breadcrumb');
    bc.innerHTML = ''; // clear previous
    const parts = path ? path.split('/') : [];

    // root/home link
    const rootLink = document.createElement('a');
    rootLink.href = "#";
    rootLink.textContent = "..";  // represents home
    rootLink.onclick = () => { goRoot(); return false; };
    bc.appendChild(rootLink);

    let acc = "";
    for(let i = 0; i < parts.length; i++){
        // add separator
        const sep = document.createTextNode(" / ");
        bc.appendChild(sep);

        acc = acc ? acc + "/" + parts[i] : parts[i];
        const a = document.createElement('a');
        a.href = "#";
        a.textContent = parts[i]; // safe textContent
        a.onclick = () => { navigate(acc); return false; };
        bc.appendChild(a);
    }
}

function goRoot(){ navigate(''); }
function navigate(p){ cwd = p; loadDir(cwd); }

function renderContent(obj){
    const content = document.getElementById('content'); 
    content.innerHTML = '';

    // directories card
    const dcard = document.createElement('div'); dcard.className='card';
    const dtitle = document.createElement('div'); dtitle.innerHTML='<strong>Folders</strong>';
    dcard.appendChild(dtitle);
    if(obj.dirs.length===0) {
        const empty = document.createElement('div');
        empty.className = 'meta';
        empty.innerHTML = '<em>(no folders)</em>';
        dcard.appendChild(empty);
    }
    for(const d of obj.dirs){
        const el = document.createElement('div'); el.className='file';
        const a = document.createElement('a');
        a.href = "#";
        a.textContent = "📁 " + d.name;
        a.onclick = () => { navigate(d.relpath); return false; };
        const meta = document.createElement('span'); meta.className='meta';
        meta.textContent = "• " + d.mtime;
        el.appendChild(a);
        el.appendChild(document.createTextNode(' '));
        el.appendChild(meta);
        dcard.appendChild(el);
    }
    content.appendChild(dcard);

    // files card
    const fcard = document.createElement('div'); fcard.className='card';
    const ftitle = document.createElement('div'); ftitle.innerHTML='<strong>Files</strong>';
    fcard.appendChild(ftitle);
    if(obj.files.length===0){
        const empty = document.createElement('div'); empty.className='meta';
        empty.innerHTML='<em>(no files)</em>';
        fcard.appendChild(empty);
    }
    for(const f of obj.files){
        const el = document.createElement('div'); el.className='file';
        const url = '/dl/' + encodeURIComponent(f.relpath);
        const a = document.createElement('a');
        a.href = url;
        a.textContent = "📄 " + f.name;
        const meta = document.createElement('span'); meta.className='meta';
        meta.textContent = `• ${f.size} • ${f.mtime}`;
        el.appendChild(a);
        el.appendChild(document.createTextNode(' '));
        el.appendChild(meta);
        fcard.appendChild(el);
    }
    content.appendChild(fcard);
}

document.getElementById('q').addEventListener('input', async (e) => {
    const q = e.target.value.trim().toLowerCase();
    if(!q) { loadDir(cwd); return; }
    const resp = await fetch('/_search?q=' + encodeURIComponent(q));
    if(!resp.ok){ return; }
    const res = await resp.json();

    // render search results safely
    const content = document.getElementById('content'); content.innerHTML = '';
    const scard = document.createElement('div'); scard.className='card';
    const stitle = document.createElement('strong');
    stitle.textContent = `Search results for "${q}" — ${res.length} files`;
    scard.appendChild(stitle);

    for(const f of res){
        const el = document.createElement('div'); el.className='file';
        const url = '/dl/' + encodeURIComponent(f.relpath);
        const a = document.createElement('a');
        a.href = url;
        a.textContent = "📄 " + f.relpath;
        const meta = document.createElement('span'); meta.className='meta';
        meta.textContent = `• ${f.size} • ${f.mtime}`;
        el.appendChild(a);
        el.appendChild(document.createTextNode(' '));
        el.appendChild(meta);
        scard.appendChild(el);
    }
    content.appendChild(scard);
});

function start(){ loadDir(cwd); }
start();

</script>
</body>
</html>
"""

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
@requires_auth
def index_page():
    # start path is empty string (root)
    start = ""
    return render_template_string(INDEX_HTML, root=str(ROOT), start=start)

@app.route("/_ls")
@requires_auth
def api_ls():
    # /_ls?path=rel/path
    rel = request.args.get("path", ".")
    if rel == ".":
        rel = ""
    # normalize: allow empty
    return jsonify(list_dir(rel))

@app.route("/_search")
@requires_auth
def api_search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])
    idx = build_index()
    out = []
    for e in idx:
        if q in e["name"].lower() or q in e["relpath"].lower():
            out.append(e)
    return jsonify(out)

@app.route("/dl/<path:relpath>")
@requires_auth
def dl(relpath):
    # serve as attachment
    target = safe_resolve(relpath)
    if not target.exists() or not target.is_file():
        abort(404)
    # parent dir and filename
    parent = str(target.parent)
    filename = target.name
    return send_from_directory(parent, filename, as_attachment=True)

# convenience route to redirect legacy patterns
@app.route("/download/<path:relpath>")
@requires_auth
def legacy_dl(relpath):
    return redirect(url_for("dl", relpath=relpath))

# ---------------------------
# Build SHORT_URLS mapping
SHORT_URLS = {}  # filename -> relpath
for root, dirs, files in os.walk(ROOT):
    root_p = pathlib.Path(root)
    rel_root = root_p.relative_to(ROOT).as_posix()
    for f in files:
        short_name = f
        if short_name in SHORT_URLS:
            # collision: append counter
            base, ext = os.path.splitext(f)
            i = 1
            while f"{base}_{i}{ext}" in SHORT_URLS:
                i += 1
            short_name = f"{base}_{i}{ext}"
        relpath = (pathlib.Path(rel_root) / f).as_posix() if rel_root != "." else f
        SHORT_URLS[short_name] = relpath

# ---------------------------
# Drop short URL route
@app.route("/drop/<filename>")
@requires_auth
def drop(filename):
    if filename not in SHORT_URLS:
        abort(404)
    return dl(SHORT_URLS[filename])

# ---------------------------

# health
@app.route("/_ping")
def ping():
    return "ok"

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    host = args.host
    port = int(args.port)
    print(f"Dropper serving root: {ROOT}")
    if AUTH:
        print("Basic auth enabled. Set DROP_AUTH=USER:PASS to change credentials.")
    else:
        print("Authentication disabled (--no-auth). Anyone can access files.")
    print(f"Open http://{host}:{port} in your browser.")
    app.run(host=host, port=port, debug=False)
