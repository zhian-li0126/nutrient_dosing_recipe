# Deploy the calculator with GitHub Pages

The interface will be on GitHub Pages. The Python/FastAPI service will run on
Render (or another Python host). This guide uses `main` as the default branch.

## 1. Choose your repository arrangement

A public GitHub repository exposes every committed file, including Python source.
The Pages workflow's `path: frontend` only limits the website artifact; it does
not change repository visibility.

To preserve a private optimizer:

1. Put this complete project in a **private backend repository**.
2. Run `python scripts/package_frontend.py` locally.
3. Extract `dist/github-pages-frontend.zip`.
4. Put the extracted contents in a separate **public frontend repository**.

Alternatively, use one private repository if your GitHub plan supports Pages from
private repositories. Use one public repository only if sharing the backend
source is intentional.

For all arrangements, upload the extracted project CONTENTS: `frontend/`,
`scripts/`, and `.github/` must sit directly at the repository root. Preserve
the `.github` directory even if your file manager hides dot-prefixed folders.
Uploading this ZIP as a single repository file will not deploy the application.

## 2. Deploy the Python service

In Render, create a new **Web Service** from the full-project repository and set:

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Root directory | Repository root (leave blank) |
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |
| Python | Selected by the included `.python-version` file: 3.12 |

Choose the available service plan that fits your use. The optional `render.yaml`
Blueprint selects the `free` plan explicitly; it does not provision anything until
you import it into Render. A sleeping service may need time to wake on first use.

Keep the full `frontend/` directory in the Python deployment. The server uses it
for local and single-host mode. Leave `frontend/config.js` unchanged in the
backend repository so its empty API base continues to use the same origin.

After deployment, copy the service's HTTPS origin, for example:

```text
https://my-nutrient-calculator.onrender.com
```

Verify `/api/health` returns `{"status":"ok"}`. The actual URL and domain are
assigned by your hosting account; the example above is a placeholder.

## 3. Set the backend CORS origin

If the Pages website will be:

```text
https://YOUR-ACCOUNT.github.io/YOUR-REPOSITORY/
```

set this environment variable in the Python hosting service:

```text
CORS_ORIGINS=https://YOUR-ACCOUNT.github.io
```

Replace `YOUR-ACCOUNT` with the real user or organization name. Omit the repository
path and trailing slash. Keep `ENABLE_API_DOCS=false` unless API documentation is
needed. Restart/redeploy the service when changing its environment.

For a custom website domain, add that exact origin instead. Multiple origins are
comma-separated. CORS governs browser access; it is not authentication and does
not make the API address confidential.

## 4. Set the frontend API address

In the repository that will publish Pages:

1. Open **Settings > Secrets and variables > Actions > Variables**.
2. Create a repository variable named **API_BASE_URL**.
3. Enter the backend HTTPS origin copied in step 2.

Use the origin only. Do not append `/api/calculate` or `/api`.

This address is public configuration, so use a repository variable. A browser
must know the address to make requests; putting it in a secret cannot hide it
after deployment. No API key is required by this implementation.

The workflow calls `scripts/configure_frontend.py` to write `frontend/config.js`
in its temporary checkout. It does not commit or alter your local file. A missing
or invalid API address stops the deployment with an explicit setup message.

## 5. Enable and publish Pages

1. Open **Settings > Pages** in the frontend repository.
2. Set **Source** to **GitHub Actions**.
3. Open **Actions > Publish calculator frontend > Run workflow**.
4. Wait for success, then open the Pages URL shown in Settings.

The `.github/workflows/deploy-pages.yml` workflow publishes only `frontend/`.
Future pushes to `main` that change the frontend or publishing helper deploy
automatically. If your branch is named differently, update the workflow branch.

Changing an Actions variable does not itself trigger a deployment. Rerun the
workflow whenever `API_BASE_URL` changes. You can also run the workflow manually
after first enabling Pages if an earlier push failed before setup was complete.

## 6. Check the real site

1. Confirm the page styling and scripts load.
2. Confirm the backend connection status becomes available.
3. Click Calculate additions with the example values.
4. Confirm fertilizer doses and predicted final concentrations appear.
5. Change an input and calculate again to confirm live API results.

The interface shows loading and API errors. It does not invent results when the
backend is unavailable. The included test suite validates the local package;
your final domain, CORS, and hosting configuration still need the above live check.

## Alternative: host the complete app together

If a `github.io` address is unnecessary, complete only step 2. The service's root
URL already serves the interface. Leave `apiBaseUrl` in `frontend/config.js`
empty and `CORS_ORIGINS` empty. Do not run the Pages workflow for this arrangement.

The code can still be maintained in a private GitHub repository.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Pages workflow says API_BASE_URL is missing | Add the Actions repository variable, then rerun the workflow |
| HTML appears but calculation fails | Verify the Python backend is running and its `/api/health` route works |
| Browser reports a CORS error | Use the exact website origin in backend CORS_ORIGINS; omit repository path |
| First request times out | A sleeping backend may be waking; wait for health to succeed and retry |
| CSS or JS returns 404 | Preserve relative paths and publish the contents of frontend/ |
| Pages is unavailable for a private repo | Check plan support or publish the frontend-only archive in a public repo |
| Python fails at startup | Deploy from the project root with requirements.txt, backend/, and frontend/ present |
| Browser still calls the old API | Rerun publishing after the variable change and refresh the page |

## Official references

- [GitHub Pages capabilities](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [GitHub Pages deployment workflow](https://docs.github.com/en/get-started/start-your-journey/deploying-your-website-automatically)
- [GitHub publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [GitHub repository visibility](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories)
- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Render Blueprint settings](https://render.com/docs/blueprint-spec)
- [Render Python version selection](https://render.com/docs/python-version)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)

These sources were checked while preparing this package on October 29, 2026.
