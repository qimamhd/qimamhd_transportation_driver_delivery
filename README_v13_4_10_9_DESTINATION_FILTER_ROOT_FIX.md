# 13.0.4.10.9 - Manual destination filter root fix

- Hardens the destination dropdown used only in manual driver-app request lines.
- Normalizes Odoo 13 many2one context values whether sent as integer ids or `[id, display_name]`.
- Adds an explicit manual-destination context marker so other destination selectors keep legacy behavior.
- If the editable one2many row has not propagated its source yet, derives the authoritative source from the driver assigned car.
- Fails closed: unresolved manual source returns no destinations instead of all destinations.
- Keeps existing XML domain, onchange filtering, pricing relation validation, and server-side create/write constraints intact.
- No API, GPS, UUID, single-device, settlement, or Flutter changes.
