"""Support for MotionMount sensors."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MotionMountSensor(coordinator, entry.entry_id)])


class MotionMountSensor(CoordinatorEntity, SensorEntity):
    """Representation of a MotionMount sensor."""

    _attr_has_entity_name = True
    _attr_name = "Turn"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-turn"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        unique_id = format_mac(self.coordinator.mm.mac.hex())

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.coordinator.mm.name,
            manufacturer="Vogel's",
            model="TVM 7675",  # TODO: This is not compatible with MainSteam motorized
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        self._attr_native_value = self.coordinator.data["turn"]
        self.async_write_ha_state()
