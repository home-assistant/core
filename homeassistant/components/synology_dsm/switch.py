"""Support for Synology DSM switch."""
from typing import Dict

from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.switch import ToggleEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import SynoApi, SynologyDSMEntity
from .const import DOMAIN, SURVEILLANCE_SWITCH, SYNO_API


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS switch."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    entities = []

    if SynoSurveillanceStation.INFO_API_KEY in api.dsm.apis:
        info = await hass.async_add_executor_job(api.dsm.surveillance_station.get_info)
        version = info["data"]["CMSMinVersion"]
        entities += [
            SynoDSMSurveillanceHomeModeToggle(
                api, sensor_type, SURVEILLANCE_SWITCH[sensor_type], version
            )
            for sensor_type in SURVEILLANCE_SWITCH
        ]

    async_add_entities(entities, True)


class SynoDSMSurveillanceHomeModeToggle(SynologyDSMEntity, ToggleEntity):
    """Representation a Synology Surveillance Station Home Mode toggle."""

    def __init__(
        self, api: SynoApi, entity_type: str, entity_info: Dict[str, str], version: str
    ):
        """Initialize a Synology Surveillance Station Home Mode."""
        super().__init__(
            api,
            entity_type,
            entity_info,
        )
        self._version = version
        self._state = None

    @property
    def is_on(self) -> bool:
        """Return the state."""
        if self.entity_type == "home_mode":
            return self._state
        return None

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return True

    async def async_update(self):
        """Update the toggle state."""
        self._state = await self.hass.async_add_executor_job(
            self._api.surveillance_station.get_home_mode_status
        )

    def turn_on(self, **kwargs) -> None:
        """Turn on Home mode."""
        self._api.surveillance_station.set_home_mode(True)

    def turn_off(self, **kwargs) -> None:
        """Turn off Home mode."""
        self._api.surveillance_station.set_home_mode(False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.surveillance_station)

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
            "sw_version": self._version,
            "via_device": (DOMAIN, self._api.information.serial),
        }
