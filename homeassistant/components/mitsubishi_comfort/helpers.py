"""Helpers shared across the Mitsubishi Comfort integration."""

from mitsubishi_comfort import DeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import CONF_ADDRESSES, CONF_CREDENTIALS, DOMAIN


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


def async_reconcile_missing_address_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Create or clear the repair from the entry's stored data alone.

    The issue is not persistent and unload deletes it, so paths that cannot
    consult the cloud's fresh device list — setup before the cloud is
    reached, a reload whose unload failed — reconcile it from the cached
    credentials and stored addresses instead.
    """
    addresses: dict[str, str] = entry.data.get(CONF_ADDRESSES, {})
    credentials: dict[str, dict[str, str]] = entry.data.get(CONF_CREDENTIALS, {})
    if any(
        dr.format_mac(cred["mac"]) not in addresses
        for cred in credentials.values()
        if has_full_credentials(cred)
    ):
        async_create_missing_address_issue(hass, entry.entry_id)
    else:
        ir.async_delete_issue(hass, DOMAIN, f"missing_address_{entry.entry_id}")


def build_credentials(devices: dict[str, DeviceInfo]) -> dict[str, dict[str, str]]:
    """Build the per-device credential cache, keyed by serial.

    discover_devices() consumes the password, cryptoSerial, and MAC
    independently, so any recovered field is worth caching — above all the
    password, which the throttled Socket.IO fetch may never return again.
    All-empty records carry nothing worth replaying and are dropped.
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
