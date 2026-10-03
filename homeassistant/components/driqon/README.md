# DRIQON for Home Assistant

DRIQON is a cloud-connected smart-home service for DRIQON devices. This Home
Assistant custom integration signs in to the DRIQON account and talks to the
cloud API at `https://api.driqon.in`. Home Assistant does not connect to the
DRIQON MQTT broker.

## Supported devices and entities

The backend currently registers `single_node` and `four_node` switch products.
For both device types it advertises the `on_off` capability, which creates one
Home Assistant `switch` entity per device. Single-node switch entities use the
included device image. Other capabilities are ignored until the DRIQON API
advertises them and a corresponding Home Assistant platform is implemented.

Devices and capabilities come from the authenticated `GET /devices` response.
The integration polls every 30 seconds, so new devices appear automatically
after the next successful refresh. Devices that are offline, absent from the
account response, or temporarily unreachable are unavailable in Home
Assistant. The integration exposes available owned and shared devices. Shared
device permissions are enforced by DRIQON: view-only shares cannot control a
switch; control and admin shares can.

Switch commands use the authenticated `POST /devices/{device_id}/command`
endpoint. DRIQON checks ownership and sharing permissions before sending a
command to the device. State is read from the cloud API; the integration does
not assume that a command changed the physical device state.

## Install

### HACS

Add the public GitHub repository
`https://github.com/DRIQON/DRIQON-BACKEND-1` in HACS:

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Enter the DRIQON GitHub repository URL and choose **Integration**.
3. Add the repository, open its DRIQON integration entry, and select **Download**.
4. Restart Home Assistant.

The repository must have a GitHub release or a default branch for HACS to
install. This repository contains one integration under
`custom_components/driqon`.

Home Assistant 2025.7 or newer is required. The DRIQON brand icon and logo
appear natively on Home Assistant 2026.3 and newer.

### Manual installation

Copy the complete `custom_components/driqon` directory into the Home Assistant
configuration directory, creating `custom_components` if necessary. The final
path should be `/config/custom_components/driqon/`. Restart Home Assistant.

## Configure

1. Go to **Settings > Devices & services > Add integration** and select
   **DRIQON**.
2. Enter the email and password used by the DRIQON mobile app.

The integration uses its bundled Firebase Web API key and the fixed DRIQON API
address, so neither is requested during setup. A Firebase Web API key is a
public project identifier, not an authorization secret; Firebase authorization
comes from the account credentials and the backend's access checks. Restrict
the key to Firebase APIs and set appropriate quotas in Google Cloud. The
integration does not contain a Firebase service-account key or Admin SDK
private key. **Never put a Firebase service-account JSON file, Admin SDK
private key, backend `.env`, MQTT credentials, or database credentials in Home
Assistant.** The password is used only during sign-in and is not stored. Home
Assistant retains the account's Firebase refresh token so it can renew access.
If that token is revoked, Home Assistant asks you to reauthenticate. Use the
integration's **Reconfigure** action to reconnect the same account.

## Examples

Turn on a DRIQON device from an automation:

```yaml
automation:
  - alias: Turn on DRIQON switch at sunset
    triggers:
      - trigger: sun
        event: sunset
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.living_room
```

Use the generated switch entities in dashboards, scripts, and other Home
Assistant automations just like other switches.

## Diagnostics and troubleshooting

Download diagnostics from the DRIQON integration's menu under **Settings →
Devices & services**. Diagnostics include the API hostname, last refresh
result, device count, device types, capabilities, online status, and share
permission. They omit the account email, device IDs and names, API key, and
Firebase tokens.

- **Cannot connect:** Check that Home Assistant can reach the DRIQON cloud API.
- **Authentication error:** Check the DRIQON email and password. Firebase
  email/password sign-in must be enabled for the project.
- **Account needs reauthentication:** Enter your current DRIQON password in
  the Home Assistant prompt.
- **Device unavailable:** Check the device's online status in DRIQON and make
  sure the account still owns or has a share for it.
- **Switch is view-only:** Ask the DRIQON device owner to grant the account
  `control` or `admin` permission.
- **A new device is missing:** Wait up to one 30-second poll interval and
  confirm the device appears in the DRIQON app under the same account.
- **The DRIQON logo is missing:** Local integration branding is supported by
  Home Assistant 2026.3 and newer. Older Home Assistant versions may show a
  generic integration icon.

## Known limitations

- The backend currently advertises only the `on_off` switch capability for
  `single_node` and `four_node` devices. Other device types and sensor, light,
  or climate capabilities are not exposed until the backend advertises a
  supported capability and the integration adds that platform.
- Device state updates are cloud-polled every 30 seconds; this integration
  does not receive MQTT telemetry directly.
- Firmware updates and pre-login local device discovery are not supported by
  the current DRIQON API integration contract.

## Security and privacy

All device discovery, state polling, and control are authenticated API
requests. This integration does not connect to MQTT or contain backend service
credentials. API failures and logs do not include passwords, access tokens,
refresh tokens, API keys, or authorization headers. Device IDs, device names,
and account emails are not included in diagnostics. The integration sends
Firebase ID tokens only to the fixed DRIQON HTTPS API host. Redirects are not
followed.

## Remove

In **Settings → Devices & services**, open DRIQON and choose **Delete**. This
removes its config entry and entities from Home Assistant. To remove the code,
delete `/config/custom_components/driqon/` and restart Home Assistant. Removing
the integration does not delete the DRIQON account or devices.

## Development

The backend repository includes the integration under
`custom_components/driqon`. Tests should mock Firebase and DRIQON HTTP calls;
never use production credentials or send test commands to physical devices.
For Home Assistant-specific config-flow tests and type/lint checks, install
the development tools from `requirements-ha-test.txt` in an isolated
environment. The repository's backend test environment does not include
Home Assistant Core.
