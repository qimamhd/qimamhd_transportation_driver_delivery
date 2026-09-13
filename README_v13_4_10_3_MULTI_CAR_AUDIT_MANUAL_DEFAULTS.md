# v13.0.4.10.3

- Settlement transfer now accepts multiple actually-used cars in one driver app batch.
- Settlement header uses the driver assigned/default car; settlement lines retain the actual car used.
- Multiple sources are still rejected because the legacy settlement header supports one source only.
- Manual app-delivery lines default the assigned driver car and its configured source.
- Destination choices are filtered by the selected source.
- Driver app fields on the employee card use chatter tracking; sensitive plaintext credentials remain non-stored.
- Unbind, unlock, and clear-credentials buttons post explicit audit messages with the acting Odoo user.
