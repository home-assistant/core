"""Support for number entities."""

from typing import Final, override

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry, alexa_api_call
from .entity import AmazonEntity

PARALLEL_UPDATES = 1

NUMBERS: Final = (
    NumberEntityDescription(
        key="amz_them_active_brightness",
        translation_key="active_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="amz_therm_inactive_brightness",
        translation_key="inactive_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices number entities based on a config entry."""

    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        known_devices.intersection_update(current_devices)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonNumberEntity(coordinator, serial_num, number_desc)
                for number_desc in NUMBERS
                for serial_num in new_devices
                if number_desc.key in coordinator.supported_sensor_keys(serial_num)
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonNumberEntity(AmazonEntity, NumberEntity):
    """Number device."""

    @property
    @override
    def native_value(self) -> int | None:
        """Return the current value."""
        value = self.coordinator.sensors[self._serial_num][
            self.entity_description.key
        ].value
        return None if value is None else int(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        sensor = self.coordinator.sensors[self._serial_num][self.entity_description.key]
        # The set_value action does not enforce the step
        range_value = round(value)
        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.call_feature_operation(
                self.device,
                sensor.feature_name,
                "setRangeValue",
                command_payload={"rangeValue": range_value},
                instance=sensor.instance or None,
            )
        # Optimistic until Amazon pushes the new state
        sensor.value = range_value
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and (
                sensor := self.coordinator.device_sensor(
                    self._serial_num, self.entity_description.key
                )
            )
            is not None
            and sensor.error is False
        )
