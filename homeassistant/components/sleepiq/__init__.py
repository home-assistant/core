"""Support for SleepIQ from SleepNumber."""
from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging

from sleepyq import Sleepyq
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import BED, DOMAIN, ICON_OCCUPIED, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_SLEEPIQ = "data_sleepiq"

DEFAULT_COMPONENT_NAME = "SleepIQ {}"
UPDATE_INTERVAL = timedelta(seconds=60)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up sleepiq component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SleepIQ config entry."""
    client = Sleepyq(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    try:
        await hass.async_add_executor_job(client.login)
    except ValueError:
        _LOGGER.error("SleepIQ login failed, double check your username and password")
        return False

    coordinator = SleepIQDataUpdateCoordinator(
        hass,
        client=client,
        update_interval=UPDATE_INTERVAL,
        username=entry.data[CONF_USERNAME],
    )

    # Call the SleepIQ API to refresh data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DATA_SLEEPIQ] = SleepIQHassData(
        coordinators={entry.data[CONF_USERNAME]: coordinator}
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DATA_SLEEPIQ].coordinators.pop(config_entry.data[CONF_USERNAME])

    return unload_ok


class SleepIQDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """SleepIQ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: Sleepyq,
        update_interval: timedelta,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{username}@SleepIQ", update_interval=update_interval
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict]:
        return await self.hass.async_add_executor_job(self.update_data)

    def update_data(self) -> dict[str, dict]:
        """Get latest data from the client."""
        return {
            bed.bed_id: {BED: bed} for bed in self.client.beds_with_sleeper_status()
        }


@dataclasses.dataclass
class SleepIQHassData:
    """Home Assistant SleepIQ runtime data."""

    coordinators: dict[str, SleepIQDataUpdateCoordinator] = dataclasses.field(
        default_factory=dict
    )


class SleepIQSensor(CoordinatorEntity):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
        name: str,
    ) -> None:
        """Initialize the SleepIQ side entity."""
        super().__init__(coordinator)
        self.bed_id = bed_id
        self.side = side

        self._async_update_attrs()

        self._attr_name = f"SleepNumber {self.bed_data.name} {self.side_data.sleeper.first_name} {SENSOR_TYPES[name]}"
        self._attr_unique_id = (
            f"{self.bed_id}_{self.side_data.sleeper.first_name}_{name}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self.bed_data = self.coordinator.data[self.bed_id][BED]
        self.side_data = getattr(self.bed_data, self.side)
