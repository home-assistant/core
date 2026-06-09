"""Helpers shared between the Mitsubishi Comfort setup and config flow."""

from mitsubishi_comfort import DeviceInfo


def build_credentials(devices: dict[str, DeviceInfo]) -> dict[str, dict[str, str]]:
    """Build the per-device credential cache, keyed by serial.

    Only fully-credentialed devices are included: a device the cloud returned
    without a password or cryptoSerial cannot be authenticated against the local
    API, so it must be re-discovered next time rather than cached as usable.
    """
    return {
        serial: {
            "password": info.password,
            "crypto_serial": info.crypto_serial,
            "mac": info.mac,
        }
        for serial, info in devices.items()
        if info.password and info.crypto_serial
    }
