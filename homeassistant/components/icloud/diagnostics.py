"""Diagnostics support for iCloud."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .account import IcloudConfigEntry, IcloudDevice
from .const import (
    DEVICE_ID,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DEVICE_NAME,
    DEVICE_PERSON_ID,
    DOMAIN,
)

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_PERSON_ID,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    "family_members",
    "owner_fullname",
    # Lost mode contact number and message.
    "ownerNbr",
    "text",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IcloudConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    account = entry.runtime_data

    data: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": entry.data,
        },
        "account": {
            "username": account.username,
            "owner_fullname": account.owner_fullname,
            "family_members": list(account.family_members_fullname.values()),
            "fetch_interval": account.fetch_interval,
            "device_count": len(account.devices),
        },
        "devices": [device.raw_status for device in account.devices.values()],
    }
    return async_redact_data(data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: IcloudConfigEntry, device: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    return async_redact_data(_get_icloud_device(entry, device).raw_status, TO_REDACT)


def _get_icloud_device(
    entry: IcloudConfigEntry, device: AnyDeviceEntry
) -> IcloudDevice:
    """Return the iCloud device linked to a device registry entry."""
    identifier = next(
        identifier for domain, identifier in device.identifiers if domain == DOMAIN
    )
    return entry.runtime_data.devices[identifier]
