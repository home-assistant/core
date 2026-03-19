# Threema Integration

Threema Gateway integration for Home Assistant. Sends E2E encrypted or simple text messages via the [Threema Gateway](https://gateway.threema.ch/) service.

User-facing documentation: https://www.home-assistant.io/integrations/threema

## Architecture

- **`__init__.py`** — Service registration (`threema.send_message`), config entry setup/unload, credential validation on startup
- **`client.py`** — `ThreemaAPIClient` wrapping the [threema.gateway SDK](https://github.com/threema-ch/threema-msgapi-sdk-python). Handles E2E (`TextMessage`) and simple (`SimpleTextMessage`) modes. Custom exceptions: `ThreemaAuthError`, `ThreemaConnectionError`, `ThreemaSendError`
- **`config_flow.py`** — Multi-step flow: setup type selection, optional key generation, credential entry with validation, reauthentication
- **`image.py`** — QR code image entity for gateway identity verification (encodes `3mid:<gateway_id>,<public_key_hex>`)
- **`const.py`** — Domain and config key constants

## Dependencies

- `threema.gateway==8.0.0` — [Official Threema Gateway SDK](https://github.com/threema-ch/threema-msgapi-sdk-python) (MIT)
- `qrcode==8.2` — QR code generation for identity verification

## Design Decisions

- **No notify entity** — `NotifyEntity.async_send_message` only accepts `message` and `title`, no recipient parameter. Threema always requires an explicit recipient, so the custom `threema.send_message` service is the proper interface.
- **Encryption downgrade protection** — Reauth flow preserves existing private keys when the field is left empty, preventing silent downgrade from E2E to simple mode.
- **Recipient validation** — Service schema validates Threema IDs with `^[0-9A-Za-z]{8}$` regex and normalizes to uppercase.
- **Multiple entry guard** — Auto-select is rejected when multiple entries are loaded; caller must specify `config_entry_id`.

## Quality Scale

Silver. See `quality_scale.yaml` for full status. Gold blockers: `diagnostics` and `reconfiguration-flow`.

## Roadmap

- Incoming messages via Gateway callback webhooks
- Image/file support via notify entity `data` parameter (camera entity snapshots, URLs, local files → Threema SDK `ImageMessage`)
- Remaining credits sensor
- Diagnostics platform
- Reconfiguration flow
