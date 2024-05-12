"""Select platform for Advantage Air integration."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirAcEntity
from .models import AdvantageAirData

ADVANTAGE_AIR_INACTIVE = "Inactive"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir select platform."""

    instance: AdvantageAirData = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    if aircons := instance.coordinator.data.get("aircons"):
        async_add_entities(AdvantageAirMyZone(instance, ac_key) for ac_key in aircons)


class AdvantageAirMyZone(AdvantageAirAcEntity, SelectEntity):
    """Representation of Advantage Air MyZone control."""

    _attr_icon = "mdi:home-thermometer"
    _attr_name = "MyZone"

    def __init__(self, instance: AdvantageAirData, ac_key: str) -> None:
        """Initialize an Advantage Air MyZone control."""
        super().__init__(instance, ac_key)
        self._attr_unique_id += "-myzone"
        self._attr_options = [ADVANTAGE_AIR_INACTIVE]
        self._number_to_name = {0: ADVANTAGE_AIR_INACTIVE}
        self._name_to_number = {ADVANTAGE_AIR_INACTIVE: 0}

        if "aircons" in instance.coordinator.data:
            for zone in instance.coordinator.data["aircons"][ac_key]["zones"].values():
                if zone["type"] > 0:
                    self._name_to_number[zone["name"]] = zone["number"]
                    self._number_to_name[zone["number"]] = zone["name"]
                    self._attr_options.append(zone["name"])

    @property
    def current_option(self) -> str:
        """Return the current MyZone."""
        return self._number_to_name[self._ac["myZone"]]

    async def async_select_option(self, option: str) -> None:
        """Set the MyZone."""
        await self.async_update_ac({"myZone": self._name_to_number[option]})
