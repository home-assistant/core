"""Helpers shared between the Mitsubishi Comfort setup and config flow."""

from mitsubishi_comfort import DeviceInfo


def is_fully_credentialed(info: DeviceInfo) -> bool:
    """Return whether the cloud returned a device's local-API credentials.

    Without a password and cryptoSerial the device cannot be authenticated
    against the local API, so it cannot be set up or cached as usable and must
    be re-discovered next time.
    """
    return bool(info.password and info.crypto_serial)


def build_credentials(devices: dict[str, DeviceInfo]) -> dict[str, dict[str, str]]:
    """Build the per-device credential cache, keyed by serial.

    Only fully-credentialed devices are included; the rest are dropped so a
    later setup re-discovers them rather than replaying unusable credentials.
    """
    return {
        serial: {
            "password": info.password,
            "crypto_serial": info.crypto_serial,
            "mac": info.mac,
        }
        for serial, info in devices.items()
        if is_fully_credentialed(info)
    }
