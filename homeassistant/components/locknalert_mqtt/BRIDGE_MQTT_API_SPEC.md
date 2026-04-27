# LocknAlert Bridge API + MQTT Broker Contract

This document describes the API contract that **this Home Assistant integration expects** from a LocknAlert bridge.

It is derived from the integration runtime and config-flow behavior.

## 1) HTTPS Bootstrap API

Base URL:

- `https://<bridge_host>:<api_port>`
- `api_port` default used by config flow: `443`
- TLS cert verification may be disabled by user (`verify_ssl=false`) for self-signed bridge certs.

### 1.1 `GET /api/info`

Purpose:

- Identify the bridge and validate that the entered/discovered serial matches the bridge.

Expected response JSON object:

```json
{
  "bridge_serial": "ABC123456"
}
```

Required fields:

- `bridge_serial` (string, non-empty)

Integration behavior:

- If response is not a JSON object: treated as invalid bootstrap.
- If `bridge_serial` missing/empty: treated as invalid bootstrap.
- If serial does not match user-provided serial: setup fails with serial mismatch.

### 1.2 `POST /api/pair`

Purpose:

- Optional pairing/auth step when a pairing token is provided by user.

Request body:

- If token provided:

```json
{ "token": "<pairing_token>" }
```

- If token omitted:

```json
{}
```

Expected success:

- Any HTTP `< 400` with JSON object body.

Integration behavior:

- `401`/`403`: invalid auth.
- `409`: pairing required.
- Any other `>=400`: cannot connect/setup error.

### 1.3 `GET /api/mqtt/bootstrap`

Purpose:

- Return MQTT runtime connection info for bridge-specific broker access.

Expected response JSON object:

```json
{
  "host": "mqtt.example.local",
  "port": 8883,
  "username": "bridge_user",
  "password": "bridge_pass",
  "tls_required": true,
  "topic_prefix": "locknalert"
}
```

Required fields:

- `host` (string)
- `port` (number)
- `username` (string)
- `password` (string)

Optional fields:

- `tls_required` (boolean, default assumed by integration: `true`)
- `topic_prefix` (string, default assumed by integration: `locknalert`)

Integration behavior:

- If any required field missing: invalid bootstrap.
- If response is not a JSON object: invalid bootstrap.

## 2) HTTP Status Semantics Expected by Integration

Across bootstrap calls (`/api/info`, `/api/pair`, `/api/mqtt/bootstrap`):

- `2xx/3xx` with JSON object => success path
- `401` or `403` => invalid auth
- `409` => pairing required
- Other `4xx/5xx` => cannot connect / setup failure

## 3) MQTT Broker Contract

After bootstrap, integration connects using returned credentials.

Connection expectations:

- Client ID format: `ha-locknalert-<bridge_serial>`
- Username/password auth required
- TLS used when `tls_required=true` (client enables TLS)
- Keepalive used by integration: `30`

Current subscription behavior in this implementation:

- Subscribes to `/#` (QoS 1)

> Note: message routing logic expects LocknAlert topic shape (below), so bridge should publish using that contract.

## 4) Topic Namespace Expected by Message Router

Router expects topics in this shape:

- `<prefix>/<bridge_id>/<kind>/...`

Where:

- `<prefix>` should match `topic_prefix` from bootstrap (default `locknalert`)
- `<bridge_id>` should be bridge serial/id used for this config entry
- `<kind>` is one of:
  - `availability`
  - `status`
  - `zone`
  - `partition`
  - `output`
  - `sensor`

### 4.1 Availability

Topic:

- `<prefix>/<bridge_id>/availability/...` (minimum 4 path segments required by parser)

Payload accepted:

- JSON object with `state: "online"|"offline"`
- Or plain text payload (`online`/`offline`), which is normalized

Published state forwarded to coordinator channel:

- `availability`

### 4.2 Status

Topic:

- `<prefix>/<bridge_id>/status/...`

Payload accepted:

- JSON object preferred, plain text tolerated

Forwarded channel:

- `status`

### 4.3 Entity-like channels

Topics (must include item id as next segment):

- `<prefix>/<bridge_id>/zone/<zone_id>/...`
- `<prefix>/<bridge_id>/partition/<partition_id>/...`
- `<prefix>/<bridge_id>/output/<output_id>/...`
- `<prefix>/<bridge_id>/sensor/<sensor_id>/...`

Forwarded channels:

- `zone:<zone_id>`
- `partition:<partition_id>`
- `output:<output_id>`
- `sensor:<sensor_id>`

## 5) Payload Format Expectations

For MQTT inbound payloads:

- If payload starts with `{`, integration attempts JSON decode.
- On JSON decode failure, payload is treated as plain string state:
  - `{ "state": "<raw_payload>" }`
- Non-JSON payloads are similarly wrapped into `{ "state": "..." }`.

Recommendation for bridge publishers:

- Prefer JSON object payloads for extensibility and typed fields.
- For availability, include explicit `state` with `online|offline`.

## 6) Discovery and Setup Expectations

For auto-discovery (mDNS/zeroconf), bridge should advertise:

- Service type: `_locknalert._tcp.local.`
- Useful TXT properties:
  - `api_port`
  - `bridge_serial`

Setup flow expectation summary:

1. User/discovery provides host + port + expected serial.
2. Integration calls `GET /api/info` and validates `bridge_serial`.
3. If pairing token supplied, calls `POST /api/pair`.
4. Integration calls `GET /api/mqtt/bootstrap`.
5. Integration stores returned MQTT credentials and starts broker client.

## 7) Minimal Bridge Compliance Checklist

A bridge implementation should provide:

- [ ] HTTPS reachable endpoint at configured host/port
- [ ] `GET /api/info` returns JSON object with `bridge_serial`
- [ ] `POST /api/pair` supports optional `{ "token": ... }`
- [ ] `GET /api/mqtt/bootstrap` returns required MQTT fields
- [ ] HTTP status semantics match this integration (`401/403`, `409`)
- [ ] MQTT broker accepts bootstrap credentials
- [ ] Topic namespace follows `<prefix>/<bridge_id>/<kind>/...`
- [ ] Availability/state payloads provided as JSON (preferred)
