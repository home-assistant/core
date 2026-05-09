# Elk E27 integration

## Overview

Use this integration to connect an Elk E27 Alarm Engine panel to Home Assistant. It
exposes alarm areas, zones, outputs, and diagnostic panel state.

## Supported devices

- Elk E27 Alarm Engine panels reachable on your local network.

## Supported features

- Alarm control panel entities for each area (arm away, arm home, arm night, disarm).
- Zone binary sensors.
- Output entities as lights and switches (on/off).
- Diagnostic sensors for panel name and connection state.

## Requirements

- The panel must be reachable from your Home Assistant instance.
- You need the panel access code and passphrase used for linking.

## Setup

You can set up the integration two ways:

- **Discover panels**: Select a panel found on the network and enter the linking
  credentials.
- **Manual setup**: Enter the panel host name or IP address and the linking
  credentials.

During setup, you will be asked for:

- `Host`: The IP address or host name of the Elk E27 panel.
- `Access code`: The panel access code used for linking. This is not a PIN.
- `Passphrase`: The panel passphrase used for linking.
- `Panel`: When multiple panels are discovered, select the one you want to add.

The integration uses the default panel port `2101` and does not ask you to set it.

## Configuration parameters

There are no configuration options after setup. If you need to change connection
details, remove the integration and add it again.

## Actions

This integration does not provide custom actions.

## Data updates

Updates are handled by the integration and are not user-configurable. The integration
keeps entities in sync with the panel and exposes changes as they arrive.

## Diagnostics

Diagnostics are available from the integration page and include connection details
and a snapshot of panel data with sensitive values redacted.

## Troubleshooting

If setup fails, check the error message:

- **Unable to connect**: Confirm the host is reachable and the panel is online.
- **Unable to authenticate**: Confirm the access code and passphrase.
- **Link required**: Enter the access code and passphrase again.
- **No panels found**: Confirm the panel is online, then retry discovery or use
  manual setup.

If arm or output actions fail with a PIN prompt, enter your alarm code in the
Home Assistant dialog.

## Removal

To remove the integration, go to **Settings → Devices & services**, select the
Elk E27 integration, and choose **Delete**.
