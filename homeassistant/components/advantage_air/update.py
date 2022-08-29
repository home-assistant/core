"""Advantage Air Update platform."""
from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir update platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    async_add_entities([AdvantageAirApp(instance)])


class AdvantageAirApp(AdvantageAirEntity, UpdateEntity):
    """Representation of Advantage Air App."""

    _attr_name = "App"

    def __init__(self, instance):
        """Initialize the Advantage Air App."""
        super().__init__(instance)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (ADVANTAGE_AIR_DOMAIN, self.coordinator.data["system"]["rid"])
            },
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self.coordinator.data["system"]["name"],
            sw_version=self.coordinator.data["system"]["myAppRev"],
        )

    @property
    def installed_version(self):
        """Return the current app version."""
        return self.coordinator.data["system"]["myAppRev"]

    @property
    def latest_version(self):
        """Return if there is an update."""
        if self.coordinator.data["system"]["needsUpdate"]:
            return "Needs Update"
        return self.installed_version
