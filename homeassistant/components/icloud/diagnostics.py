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
    DEVICE_PERSON_ID,
    DOMAIN,
)

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_ID,
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
        "account": _account_diagnostics(entry),
        "devices": [device.raw_status for device in account.devices.values()],
    }
    return async_redact_data(data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: IcloudConfigEntry, device: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    icloud_device = _get_icloud_device(entry, device)
    if icloud_device is None:
        # The account device carries the calendars and to-do lists of the
        # account, and devices iCloud no longer reports have no data at all.
        return async_redact_data({"account": _account_diagnostics(entry)}, TO_REDACT)

    return async_redact_data(icloud_device.raw_status, TO_REDACT)


def _account_diagnostics(entry: IcloudConfigEntry) -> dict[str, Any]:
    """Return the account information."""
    account = entry.runtime_data
    return {
        "username": account.username,
        "owner_fullname": account.owner_fullname,
        "family_members": list(account.family_members_fullname.values()),
        "fetch_interval": account.fetch_interval,
        "device_count": len(account.devices),
    }


def _get_icloud_device(
    entry: IcloudConfigEntry, device: AnyDeviceEntry
) -> IcloudDevice | None:
    """Return the iCloud device linked to a device registry entry, if any."""
    identifier = next(
        (identifier for domain, identifier in device.identifiers if domain == DOMAIN),
        None,
    )
    if identifier is None:
        return None

    return entry.runtime_data.devices.get(identifier)
