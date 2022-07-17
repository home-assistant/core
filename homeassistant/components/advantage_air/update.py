"""Advantage Air Update platform"""
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir sensor platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        entities.append(AdvantageAirTimeTo(instance, ac_key, "On"))
        entities.append(AdvantageAirTimeTo(instance, ac_key, "Off"))
        for zone_key, zone in ac_device["zones"].items():
            # Only show damper and temp sensors when zone is in temperature control
            if zone["type"] != 0:
                entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
                entities.append(AdvantageAirZoneTemp(instance, ac_key, zone_key))
            # Only show wireless signal strength sensors when using wireless sensors
            if zone["rssi"] > 0:
                entities.append(AdvantageAirZoneSignal(instance, ac_key, zone_key))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {vol.Required("minutes"): cv.positive_int},
        "set_time_to",
    )


class AdvantageAirTimeTo(AdvantageAirEntity, UpdateEntity):
    """Representation of Advantage Air timer control."""

    _attr_native_unit_of_measurement = ADVANTAGE_AIR_SET_COUNTDOWN_UNIT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance, ac_key, action):
        """Initialize the Advantage Air timer control."""
        super().__init__(instance, ac_key)
        self.action = action
        self._time_key = f"countDownTo{action}"
        self._attr_name = f'{self._ac["name"]} time to {action}'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-timeto{action}'
        )
