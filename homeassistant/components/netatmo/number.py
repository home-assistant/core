"""Support for a local Netatmo room temperature correction offset."""

from typing import override

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NETATMO_CREATE_CLIMATE
from .coordinator import NetatmoConfigEntry, NetatmoRoom
from .entity import NetatmoRoomEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo temperature offset number entities."""

    @callback
    def _create_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.climate_type:
            return
        async_add_entities([NetatmoRoomTemperatureOffsetNumber(netatmo_device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_CLIMATE, _create_entity)
    )


class NetatmoRoomTemperatureOffsetNumber(NetatmoRoomEntity, RestoreNumber):
    """A user-defined correction offset for a Netatmo room's measured temperature.

    Netatmo does not expose this through its public API, so the value is only
    kept in Home Assistant and never sent to the thermostat or valve.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "temperature_offset"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = -5
    _attr_native_max_value = 5
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_value = 0.0

    def __init__(self, room: NetatmoRoom) -> None:
        """Initialize the number entity."""
        super().__init__(room)
        self._attr_unique_id = f"{self.device.entity_id}-temperature_offset"

    @override
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        if (
            last_data := await self.async_get_last_number_data()
        ) is not None and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
            self.async_write_ha_state()

    @callback
    @override
    def async_update_callback(self) -> None:
        """Nothing to sync; the offset is only kept locally in Home Assistant."""

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
