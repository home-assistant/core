# Threema Integration

Developer notes for the Threema Gateway integration.

## Deferred Features (follow-up PRs)

### Path to Silver
- **Reauthentication flow** — re-enter credentials when they become invalid (branch `feature/threema-reauth`)

### Path to Gold
- **QR code image entity** — gateway identity verification via `3mid:` format (branch `feature/threema-qr`, requires `qrcode` dependency discussion)
- **Diagnostics platform** — expose gateway info, credits, configured recipients
- **Reconfiguration flow** — edit recipient name/Threema ID after creation (subentry reconfigure step)

### Future features
- Incoming messages via Gateway callback webhooks
- Image/file support (requires new platform or service — `NotifyEntity` only supports text + title)
- Remaining credits sensor
- TextSelector with PASSWORD type for secret fields
