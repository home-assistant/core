"""Demo platform that has two fake binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo binary sensor platform."""
    async_add_entities(
        [
            DemoBinarySensor(
                "binary_1",
                "Basement Floor Wet",
                False,
                BinarySensorDeviceClass.MOISTURE,
            ),
            DemoBinarySensor(
                "binary_2",
                "Movement Backyard",
                True,
                BinarySensorDeviceClass.MOTION,
            ),
            DemoBinarySensor(
                "binary_3",
                "Outside Temperature",
                False,
                BinarySensorDeviceClass.BATTERY_CHARGING,
                device_id="sensor_1",
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_name="Battery Charging",
            ),
        ]
    )


class DemoBinarySensor(BinarySensorEntity):
    """representation of a Demo binary sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: bool,
        device_class: BinarySensorDeviceClass,
        device_id: str | None = None,
        entity_category: EntityCategory | None = None,
        entity_name: str | None = None,
    ) -> None:
        """Initialize the demo sensor."""
        self._unique_id = unique_id
        self._state = state
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device_id or unique_id)
            },
            name=device_name,
        )
        self._attr_entity_category = entity_category
        self._attr_name = entity_name

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state
