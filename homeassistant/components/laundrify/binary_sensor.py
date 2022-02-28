"""Platform for binary sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from laundrify_aio.errors import ApiConnectionError, ApiUnauthorized

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""

    laundrify_api = hass.data[DOMAIN][config.entry_id]["api"]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                return await laundrify_api.get_machines()
        except ApiUnauthorized as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiConnectionError as err:
            raise UpdateFailed from err

    poll_interval = config.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="binary_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=poll_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        LaundrifyPowerPlug(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )


class LaundrifyPowerPlug(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundrify Power Plug."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        self._attr_unique_id = coordinator.data[idx]["_id"]
        self._attr_name = coordinator.data[idx]["name"]

    @property
    def device_info(self):
        """Configure the Device of this Entity."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data[self.idx]["firmwareVersion"],
        }

    @property
    def is_on(self):
        """Return entity state."""
        try:
            return self.coordinator.data[self.idx]["status"] == "ON"
        except IndexError:
            _LOGGER.warning("The backend didn't return any data for this device")
            self._attr_available = False
            return None
