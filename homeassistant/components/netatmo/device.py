"""Device registry helpers for the Netatmo integration."""

from typing import TYPE_CHECKING

import pyatmo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_URL_CONTROL, DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import NetatmoConfigEntry


@callback
def async_register_parent_devices(
    hass: HomeAssistant, entry: NetatmoConfigEntry, account: pyatmo.AsyncAccount
) -> dict[str, str]:
    """Register a device per home and map Netatmo ids to device registry ids."""
    device_registry = dr.async_get(hass)
    parent_device_ids: dict[str, str] = {}

    for home in account.homes.values():
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, home.entity_id)},
            manufacturer=MANUFACTURER,
            model="Home",
            name=home.name,
            configuration_url=CONF_URL_CONTROL,
        )
        parent_device_ids[home.entity_id] = device_entry.id

    return parent_device_ids
