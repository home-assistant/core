"""Support for locally calibrating a Netatmo room's measured temperature."""

from typing import override

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NETATMO_CREATE_CLIMATE
from .coordinator import HOME, SIGNAL_NAME, NetatmoConfigEntry, NetatmoRoom
from .entity import NetatmoRoomEntity

PARALLEL_UPDATES = 0

ATTR_OFFSET = "offset"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo true temperature number entities."""

    @callback
    def _create_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.climate_type:
            return
        async_add_entities([NetatmoRoomTrueTemperatureNumber(netatmo_device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_CLIMATE, _create_entity)
    )


class NetatmoRoomTrueTemperatureNumber(NetatmoRoomEntity, RestoreNumber):
    """A user-entered reference temperature for a Netatmo room, used to locally calibrate it.

    Netatmo's "True Temperature" calibration is not exposed through its public
    API, so this stores the correction only in Home Assistant: the value you
    enter here (for example, read from an external thermometer) is compared
    against the room's current measured temperature to compute and store an
    offset, in the `offset` attribute, for use in your own templates or
    automations. Nothing is sent to the thermostat, valve, or Netatmo's cloud.

    Once calibrated, it keeps tracking the room's measured temperature plus
    that offset, so it reflects the corrected temperature as the room's
    reading changes rather than freezing at the value you entered.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "true_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = 0
    _attr_native_max_value = 40
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_value: float | None = None
    _offset: float | None = None

    def __init__(self, room: NetatmoRoom) -> None:
        """Initialize the number entity."""
        super().__init__(room)
        self._attr_unique_id = f"{self.device.entity_id}-true_temperature"

        signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: signal_name,
                },
            ]
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None and (
            offset := last_state.attributes.get(ATTR_OFFSET)
        ) is not None:
            self._offset = offset
            self._attr_extra_state_attributes[ATTR_OFFSET] = offset

        self.async_update_callback()

    @callback
    @override
    def async_update_callback(self) -> None:
        """Track the room's measured temperature, corrected by the offset once calibrated."""
        measured_temperature = self.device.therm_measured_temperature
        if measured_temperature is None:
            return
        if self._offset is not None:
            self._attr_native_value = round(measured_temperature + self._offset, 1)
        else:
            self._attr_native_value = measured_temperature
        self.async_write_ha_state()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Calibrate against the given reference temperature."""
        measured_temperature = self.device.therm_measured_temperature
        if measured_temperature is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="measured_temperature_unknown",
                translation_placeholders={"name": self.device.name},
            )

        self._offset = round(value - measured_temperature, 1)
        self._attr_extra_state_attributes[ATTR_OFFSET] = self._offset
        self._attr_native_value = value
        self.async_write_ha_state()
