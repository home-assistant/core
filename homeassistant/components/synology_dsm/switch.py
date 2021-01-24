"""Support for Synology DSM switch."""
import logging
from typing import Dict

from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.switch import ToggleEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SynoApi, SynologyDSMCoordinatorEntity
from .const import DOMAIN, SURVEILLANCE_SWITCH, SYNO_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS switch."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    if SynoSurveillanceStation.INFO_API_KEY not in api.dsm.apis:
        return

    # initial data fetch
    coordinator = hass.data[DOMAIN][entry.unique_id]["surveillance_station_coordinator"]
    await coordinator.async_refresh()

    async_add_entities(
        SynoDSMSurveillanceHomeModeToggle(
            hass, api, sensor_type, SURVEILLANCE_SWITCH[sensor_type], coordinator
        )
        for sensor_type in SURVEILLANCE_SWITCH
    )


class SynoDSMSurveillanceHomeModeToggle(SynologyDSMCoordinatorEntity, ToggleEntity):
    """Representation a Synology Surveillance Station Home Mode toggle."""

    def __init__(
        self,
        hass: HomeAssistantType,
        api: SynoApi,
        entity_type: str,
        entity_info: Dict[str, str],
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize a Synology Surveillance Station Home Mode."""
        super().__init__(
            api,
            entity_type,
            entity_info,
            coordinator,
        )
        self._api = api
        self._hass = hass

    @property
    def homemode_data(self):
        """Camera data."""
        return self.coordinator.data["home_mode"]

    @property
    def is_on(self) -> bool:
        """Return the state."""
        if self.entity_type == "home_mode":
            return self.homemode_data["state"]
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on Home mode."""
        _LOGGER.debug("SynoDSMSurveillanceHomeModeToggle.async_turn_on()")
        await self._hass.async_add_executor_job(
            self._api.surveillance_station.set_home_mode, True
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off Home mode."""
        _LOGGER.debug("SynoDSMSurveillanceHomeModeToggle.async_turn_off()")
        await self._hass.async_add_executor_job(
            self._api.surveillance_station.set_home_mode, False
        )
        await self.coordinator.async_refresh()

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._api.information.serial,
                    SynoSurveillanceStation.INFO_API_KEY,
                )
            },
            "name": "Surveillance Station",
            "manufacturer": "Synology",
            "model": self._api.information.model,
            "sw_version": self.homemode_data["info"]["data"]["CMSMinVersion"],
            "via_device": (DOMAIN, self._api.information.serial),
        }
