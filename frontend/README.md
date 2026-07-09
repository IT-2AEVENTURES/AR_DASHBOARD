# Frontend - AR Intelligence Nexus

This frontend provides the dashboard UI for the AR analytics workflow.

## Main files
- [src/app/page.tsx](src/app/page.tsx) — dashboard, filters, upload flow, metric cards, trend/detail tabs
- [src/components/Plot.tsx](src/components/Plot.tsx) — Plotly chart wrapper
- [src/app/layout.tsx](src/app/layout.tsx) — app shell and metadata
- [src/app/globals.css](src/app/globals.css) — theme, layout, dashboard styling

## Run locally
From the frontend folder:

```bash
npm install
npm run dev
```

Then open:
- http://localhost:3000

## Environment
The frontend expects the backend API at:
- /api by default, or
- NEXT_PUBLIC_API_URL if you want to point to a different backend host

## Notes
- Upload supports .csv and .xlsx files.
- The dashboard loads snapshot data, filters, metrics, trend charts, and detail rows from the backend API.
- For LAN access, the dev server is configured to bind to 0.0.0.0.

