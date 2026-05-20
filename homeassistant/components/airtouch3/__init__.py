"""The AirTouch 3 Air Conditioner integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVERY_INTERVAL, DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import Airtouch3DataUpdateCoordinator
from .discovery import async_discover_devices, async_trigger_discovery

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CLIMATE]
type AirTouch3ConfigEntry = ConfigEntry[Airtouch3DataUpdateCoordinator]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AirTouch 3 discovery."""

    @callback
    def _async_start_background_discovery(*_: Any) -> None:
        hass.async_create_background_task(
            _async_discovery(), "airtouch3-discovery", eager_start=True
        )

    async def _async_discovery() -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVERY_TIMEOUT)
        )

    _async_start_background_discovery()
    async_track_time_interval(
        hass,
        _async_start_background_discovery,
        DISCOVERY_INTERVAL,
        cancel_on_shutdown=True,
    )
    return True


@callback
def _async_migrate_entity_unique_ids(
    hass: HomeAssistant, entry: AirTouch3ConfigEntry, host: str, system_id: str
) -> None:
    """Migrate host-based entity unique IDs to the stable system id."""
    ent_reg = er.async_get(hass)
    if not (aircon := entry.runtime_data.data):
        return

    replacements = {
        f"{host}_airtouch_ac_{aircon.ac_id}": f"{system_id}_airtouch_ac_{aircon.ac_id}"
    }
    replacements.update(
        {
            f"{host}_airtouch_{aircon.ac_id}_group_{zone.id}": (
                f"{system_id}_airtouch_{aircon.ac_id}_group_{zone.id}"
            )
            for zone in aircon.zones
        }
    )

    for old_unique_id, new_unique_id in replacements.items():
        if entity_id := ent_reg.async_get_entity_id(
            Platform.CLIMATE, DOMAIN, old_unique_id
        ):
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Set up AirTouch 3 Air Conditioner from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, host)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    if not entry.unique_id and coordinator.data.system_id:
        _async_migrate_entity_unique_ids(hass, entry, host, coordinator.data.system_id)
        hass.config_entries.async_update_entry(
            entry, unique_id=coordinator.data.system_id
        )

    _LOGGER.debug("Setting up AirTouch 3 at %s", host)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
