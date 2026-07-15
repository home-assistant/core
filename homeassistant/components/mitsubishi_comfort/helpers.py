"""Helpers shared between the Mitsubishi Comfort setup and config flow."""

from mitsubishi_comfort import DeviceInfo


def has_local_credentials(info: DeviceInfo) -> bool:
    """Return whether the cloud returned the device's local-API secrets.

    The password only comes from the rate-limited Socket.IO fetch, so a record
    with both secrets is worth caching even before the MAC is known: the next
    status fetch can supply the MAC, but a dropped password may never be
    returned again.
    """
    return bool(info.password and info.crypto_serial)


def is_fully_credentialed(info: DeviceInfo) -> bool:
    """Return whether the device can be set up: local secrets plus its MAC.

    The MAC keys the address cache, so without it the device cannot be set up
    or offered in the address repair flow yet.
    """
    return has_local_credentials(info) and bool(info.mac)


def build_credentials(devices: dict[str, DeviceInfo]) -> dict[str, dict[str, str]]:
    """Build the per-device credential cache, keyed by serial.

    Devices without local secrets are dropped so a later setup re-discovers
    them rather than replaying unusable credentials.
    """
    return {
        serial: {
            "password": info.password,
            "crypto_serial": info.crypto_serial,
            "mac": info.mac,
        }
        for serial, info in devices.items()
        if has_local_credentials(info)
    }
