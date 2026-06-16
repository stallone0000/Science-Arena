# Personal GitHub + Render Deployment

This directory is a clean copy of `../web_review_site/` for a personal fork.
The original `.git` directory was intentionally removed.

## Local check

From this directory:

```bash
python -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173/
```

## Push to your GitHub repo

Create an empty GitHub repository first, then run:

```bash
git init -b main
git add .
git commit -m "Initial personal copy of Science Arena review site"
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

If pushing over HTTPS asks for credentials, use your GitHub username and a
fine-grained personal access token. Use the smallest useful token:

- Repository access: only the target repo.
- Repository permissions: Contents read/write.
- Expiration: short, then revoke after the push if I used it for you.

Do not commit tokens, passwords, API keys, or `.env` files.

## Deploy on Render

Recommended path: use the Render Dashboard and connect your GitHub repo.
This static site does not need runtime environment variables.

Settings:

```text
Type: Static Site
Branch: main
Build Command: test -f static/data/manifest.json && echo "Using prebuilt Science Arena static data"
Publish Directory: .
```

The included `render.yaml` is also valid for a Blueprint-style setup.

If auto-deploy is enabled, every push to `main` deploys automatically. If you
prefer manual deploys, disable auto-deploy in Render and use the Dashboard's
manual deploy button.

## What secrets are needed?

No secret is needed for local edits.

For me to push to GitHub on your behalf, I need one of:

- Your already-created GitHub repo URL plus a logged-in `gh` or Git credential
  on this machine; or
- A temporary fine-grained GitHub personal access token with Contents read/write
  access to only that repo.

For me to create or manage the Render service by API, I need:

- A Render API key; and
- The target workspace/owner information, or permission to infer it from the API.

For an existing Render service, triggering deploys can also be done with that
service's deploy hook URL. Treat the deploy hook URL as a secret.
