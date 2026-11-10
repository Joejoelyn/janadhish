# JANADHISH

A premium women's clothing storefront built with React, TypeScript, FastAPI, and SQLite/PostgreSQL.

## Features
- Elegant brand styling inspired by premium Indian fashion labels
- Responsive storefront pages and catalog browsing
- Product filtering, search, and detail pages
- Cart, checkout, and custom-made clothing flows
- SQLite for local development and PostgreSQL for production
- Python backend with FastAPI and Groq AI assistant integration

## Project structure

- `backend/` — FastAPI application, models, schemas, and routes
- `web/` — React and TypeScript storefront; `npm ci` and `npm run build` produce `web/dist/`
- `frontend/` — original image assets used by the React storefront
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
5. Build the React storefront from the `web` folder:
   ```powershell
   cd web
   npm ci
   npm run build
   cd ..
   ```
6. Start the FastAPI application from the project folder:
   ```powershell
   python -m backend.manage_schema
   python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```
7. Open `http://127.0.0.1:8000/`. FastAPI serves the storefront, its static
   files, and API routes from the same origin.

## Deploy to a domain

The project includes a Render Blueprint (`render.yaml`) for hosting the FastAPI
site. Configure a PostgreSQL connection for production; SQLite remains the
local-development default.

1. Push the project to a GitHub repository. Do not upload `.env` or a local
   database file; `.gitignore` excludes both.
2. Create a PostgreSQL database in Render and copy its **internal** connection URL.
3. In Render, choose **New > Blueprint** and connect the repository. When prompted,
   enter the internal URL as `DATABASE_URL` and an HTTPS origin you control as
   `PUBLIC_SITE_URL`. Product sharing links and the sitemap use that origin.
   Do not commit the database URL to source control.
4. Deploy using `render.yaml`. Set `FRONTEND_ORIGIN` only if the React app is
   hosted on a separate origin. For an existing Blueprint, set new `sync: false`
   variables in the service settings because Render prompts only at creation.
5. If using a custom domain, add your verified domain in the Render service settings.
   Follow the DNS records Render shows in your domain registrar's DNS settings.
   Add a `www` address too if you want it, and update `PUBLIC_SITE_URL` to the
   final canonical HTTPS address.
6. Wait for Render to verify DNS and issue HTTPS, then open your site.

Render builds the React frontend and FastAPI backend with the multi-stage `Dockerfile`.
The container applies reviewed Alembic migrations before starting the FastAPI service.
An existing database is stamped at the initial revision only when its schema matches
the baseline exactly; a mismatch stops startup for manual review instead of changing
customer data. Back up the database before each production schema upgrade.

For later model changes, generate an Alembic revision against a disposable database
with `alembic revision --autogenerate -m "describe change"`, review the generated
operations, and rehearse `python -m backend.manage_schema` on a database backup.

```text
Frontend build: npm ci && npm run build
Backend build: pip install -r requirements.txt
Start: python -m backend.manage_schema && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

FastAPI serves the React build at `/`, plus original image assets and API routes.
Public product pages expose product-specific sharing metadata. `/sitemap.xml`
lists active products, while `/robots.txt` excludes account, checkout, admin,
and API routes from crawling. Unknown storefront URLs return HTTP 404.
The frontend uses a relative
API base by default, so browser requests such as `/api/products` and
`/api/auth/login` go to the same domain without a separately hosted frontend.
Keep the generated `SECRET_KEY` private. If you already have production orders
or customer data, back up the database before changing hosting or storage.

## API docs

## QR payment operations

Checkout currently offers only the supplied UPI QR for Kiran Lodha. The customer
must enter the exact displayed INR total in their UPI app and submit the
transaction reference. Submitting a reference never marks an order paid.
The bag is cleared when the QR order is created; pieces added afterward remain
in the bag when the earlier order's reference is submitted.
Private order links use `/checkout#payment=...`; the browser sends the token in
the body of payment API requests, not in request URLs. Older query-string links
still open and are replaced in the browser address bar after loading.

An authorised reviewer signs in at `/admin/payments`. Submitted references
appear in the review queue; orders without a reference remain in a separate
awaiting queue. The reviewer matches the reference,
recipient account, and exact amount against the receiving bank statement, then
approves or rejects the payment. A rejected reference can be replaced; each
reference can be used for only one order. A customer can request cancellation;
the reserved stock stays held until a reviewer confirms that the receiving
account has no matching deposit and cancels the order. A customer who paid
before requesting cancellation can still submit the transaction reference.
The completed-history view retains approval, rejection, cancellation, and
completed-refund records. Staff record a refund only after confirming its
outgoing bank or UPI transaction; the site does not transfer money.
Payments sent without a submitted reference require manual investigation in
the receiving account.

After verification, `/admin/fulfillment` shows paid orders in an open work
queue. Staff can mark them packed, shipped with carrier and tracking reference,
then delivered. Delivered orders remain available in a separate history view;
customers can check delivery status from their order page.

Create a regular account first, then grant full store admin access from a trusted
server shell with `python -m backend.manage_admin your@email.com --grant`.
This grants payment review, fulfilment, customer inbox, and catalog management.
Revoke it with `--revoke`. Sign in again after a grant; an earlier customer
session cannot open admin pages. Grant this role only to staff authorized for
all four areas, including the receiving account statement. Keep `SECRET_KEY`
stable and private, and use a persistent PostgreSQL database for production.

For the local Docker preview, run the grant command inside its container:
`docker exec janadhish-qr-final-preview python -m backend.manage_admin your@email.com --grant`.
The preview mounts the ignored `.preview-data/` directory at `/app/data` and
uses `DATABASE_URL=sqlite:////app/data/janadhish.db` so accounts, orders, and
catalog edits and uploaded product photos survive container replacement.

The owner confirmed on 2026-11-07 that Kiran Lodha is authorised to receive
JANADHISH payments through the supplied QR. Before public launch, test the QR
against a real UPI app with a small owner-controlled
transaction, and reconcile it in `/admin/payments`.

## Customer requests

The custom-made form collects garment-specific measurements, a fabric, a design,
and customer contact details. These are requests for a quote, not paid orders.
An authorised reviewer can view them alongside contact messages at
`/admin/inbox` and mark a custom request pending, reviewed, or closed.
The contact form returns a JD ticket number and a private tracking link in the
page address. Customers can revisit that link to see status and staff replies;
the site does not send an email notification. Reviewers post replies and update
status in `/admin/inbox`. Each change is retained in an admin audit history,
and resolving a ticket requires a customer-visible reply.

## Catalog operations

The startup catalog adds products with new SKUs; it does not overwrite existing
product details, prices, visibility, or stock. An authorised administrator can
add a product at `/admin/catalog` with a unique SKU, collection, prices, stock,
descriptions, sizes, colours, and 1–6 JPEG, PNG, or WebP photos. Leave “Visible in
store” off to save a draft, then publish it after review. Staff can edit those
values and replace a product's full photo gallery on the same page. Each upload
must be 10 MB or smaller; the server validates and converts it to WebP. Uploaded
photos are stored in the database, so use persistent database storage and include
it in backups. Standard and with-pads prices shown on product pages are the same
database prices used by checkout. Product changes are recorded in an admin-only
history. Custom fabric and design choices also come from active database records.

- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

## Notes
- The active storefront is React and TypeScript. The server requires a React build; archived HTML pages are not served.
- Product photos are organized by collection under `frontend/Images/products/`;
  the product catalog serves those images and details through the FastAPI API.
  The API serves smaller WebP copies when available and keeps the original image
  paths in the database. After adding or changing product photos, install Pillow
  in a local authoring environment and run `python scripts/optimize_product_images.py`.
- The logo is stored at `frontend/Images/logo/logo.png`.
