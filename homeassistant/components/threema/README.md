# Threema Integration

Threema Gateway integration for Home Assistant. Sends E2E encrypted or simple text messages via the [Threema Gateway](https://gateway.threema.ch/) service.

User-facing documentation: https://www.home-assistant.io/integrations/threema

## Architecture

- **`__init__.py`** — Config entry setup/unload, credential validation on startup
- **`config_flow.py`** — Multi-step flow: setup type selection, optional key generation, credential entry with validation, reauthentication. Subentry flow for adding recipients.
- **`notify.py`** — `NotifyEntity` per recipient (configured via subentries). Sends text messages via the Threema SDK.
- **`client.py`** — `ThreemaAPIClient` wrapping the [threema.gateway SDK](https://github.com/threema-ch/threema-msgapi-sdk-python). Handles E2E (`TextMessage`) and simple (`SimpleTextMessage`) modes. Custom exceptions: `ThreemaAuthError`, `ThreemaConnectionError`, `ThreemaSendError`
- **`image.py`** — QR code image entity for gateway identity verification (encodes `3mid:<gateway_id>,<public_key_hex>`)
- **`const.py`** — Domain and config key constants

## Dependencies

- `threema.gateway==8.0.0` — [Official Threema Gateway SDK](https://github.com/threema-ch/threema-msgapi-sdk-python) (MIT)
- `qrcode==8.2` — QR code generation for identity verification

## Design Decisions

- **NotifyEntity with subentries** — Each recipient is a subentry creating a `NotifyEntity`. This integrates with HA's notify groups (send to Threema + Telegram + Alexa in one action) and follows the platform-first architecture.
- **Encryption downgrade protection** — Reauth flow preserves existing private keys when the field is left empty, preventing silent downgrade from E2E to simple mode.
- **Recipient validation** — Subentry flow validates Threema IDs with `^[0-9A-Za-z]{8}$` regex and normalizes to uppercase.
- **client.py as glue code** — The SDK handles all API communication. client.py maps SDK exceptions to HA-specific types and manages connection context.

## Quality Scale

Silver. See `quality_scale.yaml` for full status. Gold blockers: `diagnostics` and `reconfiguration-flow`.

## Roadmap

- Incoming messages via Gateway callback webhooks
- Image/file support (requires new platform or service — `NotifyEntity` only supports text + title)
- Remaining credits sensor
- Diagnostics platform
- Reconfiguration flow
