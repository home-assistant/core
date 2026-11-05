"""Services for the DoorBird integration."""

import aiohttp
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .models import DoorBirdConfigEntry
from .util import async_get_entries

SERVICE_RESTART = "restart"

RESTART_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_DEVICE_ID): cv.ensure_list}
)


async def _async_restart(call: ServiceCall) -> None:
    """Restart the targeted DoorBird devices."""
    hass = call.hass
    device_registry = dr.async_get(hass)
    loaded_entries = {entry.entry_id: entry for entry in async_get_entries(hass)}

    # Resolve every target before restarting anything, so a bad target
    # does not leave some devices restarted and others not.
    entries: list[DoorBirdConfigEntry] = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = device_registry.async_get(device_id)
        entry_id = None
        if device is not None:
            entry_id = next(
                (id_ for id_ in device.config_entries if id_ in loaded_entries), None
            )
        if entry_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="device_not_found"
            )
        entries.append(loaded_entries[entry_id])

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
    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, _async_restart, schema=RESTART_SERVICE_SCHEMA
    )
