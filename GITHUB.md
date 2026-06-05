# GitHub — ProjectAce (p1)

This folder is its **own Git repository** (not the parent `ace/` folder).

## Ignored locally (not pushed)

- `docs/developer-guide.html`
- `.venv/`, `.env`, `*.db`, `.pytest_cache/`
- `server/`, `instance/` (old scaffold)

## First-time setup

```powershell
cd p1
git init
git add .
git status
git commit -m "Initial commit: ProjectAce POC"
```

## Create GitHub repo & push

1. On GitHub: **New repository** → name e.g. `projectace-poc` → **no** README/license (already in folder).
2. Then:

```powershell
git remote add origin https://github.com/YOUR_USER/projectace-poc.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USER` and repo name with yours.
