"""Services for the DoorBird integration."""

import aiohttp
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .models import DoorBirdConfigEntry
from .util import async_get_entries

SERVICE_RESTART = "restart"

RESTART_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_DEVICE_ID): probatio.EnsureList()}
)


async def _async_restart(call: ServiceCall) -> None:
    """Restart the targeted DoorBird devices."""
    hass = call.hass
    loaded_entries = {entry.entry_id: entry for entry in async_get_entries(hass)}

    # Resolve every target before restarting anything, so a bad target
    # does not leave some devices restarted and others not.
    entries: list[DoorBirdConfigEntry] = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        _, config_entry = dr.async_get_device_and_config_entry_for_domain(
            hass, device_id, domain=DOMAIN
        )
        if config_entry is None or config_entry.entry_id not in loaded_entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="device_not_found"
            )
        entries.append(loaded_entries[config_entry.entry_id])

    for entry in entries:
        door_station = entry.runtime_data.door_station
        name = door_station.name or entry.title
        try:
            restarted = await door_station.device.restart()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="restart_failed",
                translation_placeholders={"name": name},
            ) from err
        if not restarted:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="restart_failed",
                translation_placeholders={"name": name},
            )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the DoorBird services."""
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RESTART, _async_restart, schema=RESTART_SERVICE_SCHEMA
    )
