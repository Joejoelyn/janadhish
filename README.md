# JANADHISH

A premium women's clothing storefront built with FastAPI, SQLite, and vanilla HTML/CSS/JS.

## Features
- Elegant brand styling inspired by premium Indian fashion labels
- Responsive storefront pages and catalog browsing
- Product filtering, search, and detail pages
- Cart, checkout, and custom-made clothing flows
- SQLite database with clean upgrade path to PostgreSQL
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
5. Open two PowerShell terminals in the project folder. Start the backend in
   the first terminal:
   ```powershell
   python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```
6. Start the separate frontend server in the second terminal:
   ```powershell
   python frontend_server.py
   ```
7. Open `http://127.0.0.1:5500/` in the browser. The frontend server serves
   pages and static files on port `5500` and proxies API requests to FastAPI on
   port `8000`. Keep both terminals open while using the site. Press `Ctrl+C`
   in each terminal to stop its server.

## Deploy to a domain

The project includes a Render Blueprint (`render.yaml`) for hosting the FastAPI
site with a persistent SQLite disk. The Starter web service and persistent disk
are paid Render resources; the domain registration is separate.

1. Push the project to a GitHub repository. Do not upload `.env` or a local
   database file; `.gitignore` excludes both.
2. In Render, choose **New > Blueprint**, connect the repository, and deploy
   using `render.yaml`.
3. In the Render service settings, add `janadhish.co.in` as a custom domain.
   Follow the DNS records Render shows in your domain registrar's DNS settings.
   Add `www.janadhish.co.in` too if you want the `www` address.
4. Wait for Render to verify DNS and issue HTTPS, then open
   `https://janadhish.co.in`.

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
