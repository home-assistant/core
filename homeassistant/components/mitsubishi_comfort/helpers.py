"""Helpers shared across the Mitsubishi Comfort integration."""

from mitsubishi_comfort import DeviceInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def is_fully_credentialed(info: DeviceInfo) -> bool:
    """Return whether the device can be set up: local secrets plus its MAC.

    Without a password and cryptoSerial the device cannot be authenticated
    against the local API, and the MAC keys the address cache, so without it
    the device cannot be set up or offered in the address repair flow yet.
    """
    return bool(info.password and info.crypto_serial and info.mac)


def has_full_credentials(cred: dict[str, str]) -> bool:
    """Return whether a cached record holds the secrets plus MAC setup needs."""
    return bool(cred["password"] and cred["crypto_serial"] and cred["mac"])


def async_create_missing_address_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Raise the fixable repair offering manual entry of missing LAN addresses."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"missing_address_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="missing_address",
        data={"entry_id": entry_id},
    )


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
