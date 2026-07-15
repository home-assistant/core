"""Helpers shared between the Mitsubishi Comfort setup and config flow."""

from mitsubishi_comfort import DeviceInfo


def is_fully_credentialed(info: DeviceInfo) -> bool:
    """Return whether the device can be set up: local secrets plus its MAC.

    Without a password and cryptoSerial the device cannot be authenticated
    against the local API, and the MAC keys the address cache, so without it
    the device cannot be set up or offered in the address repair flow yet.
    """
    return bool(info.password and info.crypto_serial and info.mac)


def build_credentials(devices: dict[str, DeviceInfo]) -> dict[str, dict[str, str]]:
    """Build the per-device credential cache, keyed by serial.

    discover_devices() consumes the password, cryptoSerial, and MAC
    independently, so any recovered field is worth caching — above all the
    password, which the throttled Socket.IO fetch may never return again.
    All-empty records are dropped so a later setup re-discovers the device.
    """
    return {
        serial: {
            "password": info.password,
            "crypto_serial": info.crypto_serial,
            "mac": info.mac,
        }
        for serial, info in devices.items()
        if info.password or info.crypto_serial or info.mac
    }
