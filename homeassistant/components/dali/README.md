# Tridonic DALI

The Tridonic DALI integration connects Home Assistant to Lunatone USB-DALI2 interfaces and the DALI control gears attached to them.

## Installation

1. Connect a Lunatone USB-DALI2 interface to the Home Assistant host.
2. Connect the DALI control gear to the interface and assign each ballast a unique DALI short address.
3. In Home Assistant, open **Settings > Devices & services**.
4. Select **Add integration** and choose **Tridonic DALI**.
5. Confirm the discovered USB-DALI2 interface.

The interface must be available as a serial device. Home Assistant uses the stable serial device path when configuring the integration.

## Devices and updates

The integration refreshes the state of known control gear every 30 seconds and rescans the full DALI short-address range for new or removed gear every five minutes. Each responding control gear is added as a light. Gear that stops responding becomes unavailable, and newly responding gear is added automatically.

## Control

Lights support on, off, and brightness control. The integration currently supports dimmable LED control gear (DALI device type 6, IEC 62386-207) and exposes it as brightness-only lights.

## Removal

1. Open **Settings > Devices & services**.
2. Select **Tridonic DALI**.
3. Open the configured USB-DALI2 interface and select the menu.
4. Select **Delete**.
5. Disconnect the USB-DALI2 interface if it is no longer needed.

No device-side removal step is required.
