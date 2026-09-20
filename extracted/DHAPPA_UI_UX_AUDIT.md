# DHAPPA UI/UX Audit

## Findings before refactor
- Navigation exposed every engine as a peer tab, increasing scanning cost.
- The first screen opened in a research-heavy consensus view instead of an operational command center.
- Header controls and page content competed for attention.
- House cards had useful data but lacked a shared decision hierarchy.
- Technical engine metadata and raw metrics were too close to primary results.
- Import and daily data workflows needed one canonical visual surface.

## Changes made
- Added shared application frame with collapsible sidebar and target header.
- Added Dashboard route with latest data, next target, integrity, registry, and four house cards.
- Added searchable Engine Lab registry/detail layout.
- Preserved consensus and engine rendering from existing evaluation payloads.
- Preserved Daily Data table, filters, pagination, import preview, edit, add, and export workflows.
- Added loading, error, status, focus, responsive, and empty-state treatments.
- Added centralized design tokens in the shared stylesheet.

## Intentionally unchanged
Prediction calculations, consensus weighting, historical data, validation rules, backups, metrics rebuild, and canonical save flow.
