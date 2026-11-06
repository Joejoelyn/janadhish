# JANADHISH

A premium women's clothing storefront built with FastAPI, SQLite/PostgreSQL, and vanilla HTML/CSS/JS.

## Features
- Elegant brand styling inspired by premium Indian fashion labels
- Responsive storefront pages and catalog browsing
- Product filtering, search, and detail pages
- Cart, checkout, and custom-made clothing flows
- SQLite for local development and PostgreSQL for production
- Python backend with FastAPI and Groq AI assistant integration

## Project structure

- `backend/` — FastAPI application, models, schemas, and routes
- `frontend/` — storefront HTML, CSS, JS, and image assets
- `.env.example` — environment variable template
- `requirements.txt` — Python dependency list

## Setup

1. Open the project folder in VS Code or Command Prompt.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Create a `.env` file from `.env.example` and add your local secret values.
5. Start the FastAPI application from the project folder:
   ```powershell
   python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```
6. Open `http://127.0.0.1:8000/`. FastAPI serves the storefront, its static
   files, and API routes from the same origin. The optional
   `frontend_server.py` remains available for the existing proxy-based local
   workflow.

## Deploy to a domain

The project includes a Render Blueprint (`render.yaml`) for hosting the FastAPI
site. Configure a PostgreSQL connection for production; SQLite remains the
local-development default.

1. Create a PostgreSQL database in Render and set the web service's
   `DATABASE_URL` to its **internal** connection URL. The Blueprint prompts for
   this value; do not commit it to source control.
2. Set `FRONTEND_ORIGIN` to the allowed frontend origins, comma-separated if
   needed (for example, `https://janadhish.co.in,https://www.janadhish.co.in`).
3. Push the project to a GitHub repository. Do not upload `.env` or a local
   database file; `.gitignore` excludes both.
4. In Render, choose **New > Blueprint**, connect the repository, and deploy
   using `render.yaml`.
5. In the Render service settings, add `janadhish.co.in` as a custom domain.
   Follow the DNS records Render shows in your domain registrar's DNS settings.
   Add `www.janadhish.co.in` too if you want the `www` address.
6. Wait for Render to verify DNS and issue HTTPS, then open
   `https://janadhish.co.in`.

Render builds and starts this single FastAPI service with:

```text
Build: pip install -r requirements.txt
Start: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

FastAPI serves the existing `frontend/` directory, including the storefront at
`/`, static assets, and the existing API routes. The frontend uses a relative
API base by default, so browser requests such as `/api/products` and
`/api/auth/login` go to the same domain without a separately hosted frontend.
Keep the generated `SECRET_KEY` private. If you already have production orders
or customer data, back up the database before changing hosting or storage.

## API docs
- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

## Notes
- The frontend is intentionally static HTML and JS to match the required stack.
- Product photos are organized by collection under `frontend/Images/products/`;
  the product catalog serves those images and details through the FastAPI API.
- The logo is stored at `frontend/Images/logo/logo.png`.
