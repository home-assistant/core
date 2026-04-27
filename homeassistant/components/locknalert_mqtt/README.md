# LocknAlert Home Assistant Component

LocknAlert is a standalone Home Assistant integration (`domain: locknalert`) for LocknAlert Paradox bridges.

## Installation and setup

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **LocknAlert**.
3. If your bridge is discovered automatically over mDNS, confirm the detected host.
4. If not discovered, enter:
   - Bridge host/IP
   - API port (default: `9443`)
   - Bridge serial
   - Optional pairing token (if your bridge requires pairing)
   - Optional SSL verification toggle for self-signed certificates
5. After validation, the integration stores LocknAlertLocknAlertMQTT bootstrap credentials and starts runtime transport.

## Configuration parameters

The config flow stores these entry values:

- `host`: Bridge host used for HTTPS bootstrap.
- `port`: Bridge HTTPS API port.
- `verify_ssl`: SSL certificate verification for bridge bootstrap requests.
- `bridge_serial`: Unique bridge identifier used as config-entry unique ID.
- `mqtt.host`: Runtime LocknAlertLocknAlertMQTT broker host issued by bridge bootstrap.
- `mqtt.port`: Runtime LocknAlertLocknAlertMQTT broker port.
- `mqtt.username` / `mqtt.password`: Runtime broker credentials issued by bridge.
- `mqtt.tls_required`: Whether TLS is required by broker.
- `mqtt.topic_prefix`: Topic prefix used by this integration.

## Architecture

1. **Discovery**: The bridge advertises `_locknalert._tcp.local.` over Zeroconf/mDNS.
2. **Secure bootstrap**: The config flow connects to the bridge over HTTPS (`/api/info`, optional `/api/pair`, `/api/mqtt/bootstrap`). Certificate verification can be disabled for self-signed bridge certs (default behavior).
3. **Runtime transport**: The integration opens its own LocknAlertLocknAlertMQTT client using bridge-issued credentials.
4. **Entity model**: Bridge payloads are intended to align with standard Home Assistant LocknAlertLocknAlertMQTT topic conventions.

## Topic model

The bridge broker publishes standard Home Assistant LocknAlertLocknAlertMQTT topics, including
`homeassistant/<component>/<id>/config` discovery payloads and matching state
topics for entities.

This integration handles onboarding and broker bootstrap, and then uses LocknAlertMQTT
with normal Home Assistant topic semantics.

## Platforms

Current platform support:

- `binary_sensor` (zones)
- `sensor` (bridge diagnostics)
- `switch` (outputs / PGMs)
- `alarm_control_panel` (partitions)

Planned scaffolding exists for:

- `lock`
- `cover`

## Notes on LocknAlertLocknAlertMQTT pattern reuse

The integration borrows lifecycle ideas from Home Assistant's LocknAlertLocknAlertMQTT integration:

- one broker client per config entry
- reconnect and re-subscribe behavior
- central message dispatch to a shared coordinator

It does **not** override or depend on the built-in `mqtt` integration for onboarding or entity creation.

## Troubleshooting

- **Cannot connect / setup fails**: Verify bridge reachability and API port, then retry setup.
- **Invalid auth / pairing required**: Provide a valid pairing token and re-run setup or reauthentication.
- **Bridge offline**: Runtime availability is updated from LocknAlertLocknAlertMQTT availability/status topics; devices recover automatically after reconnect.
- **Serial mismatch error**: Ensure you are pairing the intended bridge and that the entered bridge serial matches the bridge API response.

## Reauthentication

If bridge credentials are rotated or pairing expires, Home Assistant can trigger reauthentication for this config entry. The flow re-validates the bridge and refreshes stored LocknAlertLocknAlertMQTT credentials.

## Bridge API and MQTT contract

For implementers of LocknAlert bridges, see `BRIDGE_MQTT_API_SPEC.md` for the exact HTTPS bootstrap and MQTT topic/payload contract this integration expects.
