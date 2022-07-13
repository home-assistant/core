"""Select platform for Advantage Air integration."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity

ADVANTAGE_AIR_INACTIVE = "Inactive"
ADVANTAGE_AIR_MYAUTO = "MyAuto"
ADVANTAGE_AIR_MYTEMP = "MyTemp"
ADVANTAGE_AIR_MYZONE = "MyZone"
# ADVANTAGE_AIR_MYAUTO_ENABLE = "myAutoModeIsRunning"
# ADVANTAGE_AIR_MYTEMP_ENABLE = "climateControlModeIsRunning"
ADVANTAGE_AIR_MYAUTO_ENABLE = "myAutoModeEnabled"
ADVANTAGE_AIR_MYTEMP_ENABLE = "climateControlModeEnabled"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir select platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[SelectEntity] = []
    for ac_key in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirMyZone(instance, ac_key))
        entities.append(AdvantageAirAutoMode(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirMyZone(AdvantageAirEntity, SelectEntity):
    """Representation of Advantage Air MyZone control."""

    _attr_icon = "mdi:home-thermometer"
    _attr_options = [ADVANTAGE_AIR_INACTIVE]
    _number_to_name = {0: ADVANTAGE_AIR_INACTIVE}
    _name_to_number = {ADVANTAGE_AIR_INACTIVE: 0}
    _attr_name = "MyZone"

    def __init__(self, instance, ac_key):
        """Initialize an Advantage Air MyZone control."""
        super().__init__(instance, ac_key)
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-myzone'
        )

        # Add option for each zone that supports MyZone
        for zone in instance["coordinator"].data["aircons"][ac_key]["zones"].values():
            if zone["type"] > 0:
                self._name_to_number[zone["name"]] = zone["number"]
                self._number_to_name[zone["number"]] = zone["name"]
                self._attr_options.append(zone["name"])

        # Disable this entity if there is only 1 option
        self._attr_entity_registry_enabled_default = len(self._attr_options) > 1

    @property
    def current_option(self):
        """Return the current myZone."""
        return self._number_to_name[self._ac["myZone"]]

    async def async_select_option(self, option):
        """Set the MyZone."""
        await self.async_change(
            {self.ac_key: {"info": {"myZone": self._name_to_number[option]}}}
        )


class AdvantageAirAutoMode(AdvantageAirEntity, SelectEntity):
    """Representation of Advantage Air Auto Selector."""

    _attr_icon = "mdi:thermostat-auto"
    _attr_options = [ADVANTAGE_AIR_MYZONE]

    def __init__(self, instance, ac_key):
        """Initialize an Advantage Air Auto Selector."""
        super().__init__(instance, ac_key)
        self._attr_name = f'{self._ac["name"]} auto mode'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-automode'
        )

        # Add option for each supported auto mode
        if ADVANTAGE_AIR_MYAUTO_ENABLE in self._ac:
            self._attr_options.push(ADVANTAGE_AIR_MYAUTO)
        if ADVANTAGE_AIR_MYTEMP_ENABLE in self._ac:
            self._attr_options.push(ADVANTAGE_AIR_MYTEMP)

        # Disable this entity if there is only 1 option
        self._attr_entity_registry_enabled_default = len(self._attr_options) > 1

    @property
    def current_option(self):
        """Return the enabled auto mode."""
        if (
            ADVANTAGE_AIR_MYAUTO_ENABLE in self._ac
            and self._ac[ADVANTAGE_AIR_MYAUTO_ENABLE]
        ):
            return ADVANTAGE_AIR_MYAUTO
        if (
            ADVANTAGE_AIR_MYTEMP_ENABLE in self._ac
            and self._ac[ADVANTAGE_AIR_MYTEMP_ENABLE]
        ):
            return ADVANTAGE_AIR_MYTEMP
        return ADVANTAGE_AIR_MYZONE

    async def async_select_option(self, option):
        """Set the auto mode."""
        await self.async_change(
            {
                self.ac_key: {
                    "info": {
                        ADVANTAGE_AIR_MYAUTO_ENABLE: option == ADVANTAGE_AIR_MYAUTO,
                        ADVANTAGE_AIR_MYTEMP_ENABLE: option == ADVANTAGE_AIR_MYTEMP,
                    }
                }
            }
        )
