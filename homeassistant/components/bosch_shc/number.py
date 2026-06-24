"""Platform for number integration."""

from typing import override

from boschshcpy import SHCDevice
from boschshcpy.models_impl import SHCMicromoduleRelay

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC number platform."""
    session = config_entry.runtime_data
    parent_id = session.information.unique_id
    entities: list[NumberEntity] = []

    for device in (
        *session.device_helper.thermostats,
        *session.device_helper.roomthermostats,
    ):
        entities.append(
            SHCThermostatOffsetNumber(
                device=device,
                parent_id=parent_id,
                entry_id=config_entry.entry_id,
            )
        )
        if (
            getattr(device, "supports_display_configuration", False)
            and device.display_brightness is not None
        ):
            entities.append(
                SHCDisplayBrightnessNumber(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            getattr(device, "supports_display_configuration", False)
            and device.display_on_time is not None
        ):
            entities.append(
                SHCDisplayOnTimeNumber(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )

    entities.extend(
        SHCImpulseLengthNumber(
            device=device,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.micromodule_impulse_relays
        if device.impulse_length is not None
    )

    async_add_entities(entities)


class SHCThermostatOffsetNumber(SHCEntity, NumberEntity):
    """Number entity for TRV / wall-thermostat temperature offset."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "thermostat_offset"

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize the thermostat offset number."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_offset"

    @property
    @override
    def native_value(self) -> float:
        """Return the current offset."""
        return self._device.offset

    @property
    @override
    def native_step(self) -> float:
        """Return the step size."""
        return self._device.step_size

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum offset."""
        return self._device.min_offset

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum offset."""
        return self._device.max_offset

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the temperature offset, clamped to the device range."""
        clamped = max(self.native_min_value, min(self.native_max_value, value))
        await self.hass.async_add_executor_job(setattr, self._device, "offset", clamped)


class SHCImpulseLengthNumber(SHCEntity, NumberEntity):
    """Number entity for the impulse length of a Micromodule Relay in impulse mode.

    The lib stores impulse_length in tenths of seconds (units of 100 ms).
    We expose it in seconds (range 1-60 s, step 0.1 s) for user-friendly display.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_max_value = 60.0
    _attr_native_min_value = 1.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_translation_key = "impulse_length"

    def __init__(
        self, device: SHCMicromoduleRelay, parent_id: str, entry_id: str
    ) -> None:
        """Initialize the impulse-length number."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_impulse_length"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the impulse length in seconds."""
        raw = self._device.impulse_length
        return None if raw is None else raw / 10.0

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the impulse length (converted from seconds to tenths of seconds)."""
        clamped = max(
            self._attr_native_min_value, min(self._attr_native_max_value, value)
        )
        raw = round(clamped * 10)
        await self.hass.async_add_executor_job(
            setattr, self._device, "impulse_length", raw
        )


class SHCDisplayBrightnessNumber(SHCEntity, NumberEntity):
    """Number entity for the display brightness of a TRV Gen2 or Room Thermostat 2."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1.0
    _attr_translation_key = "display_brightness"

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize the display-brightness number."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_display_brightness"

    @property
    @override
    def native_min_value(self) -> float:
        """Return minimum brightness from the device."""
        val = getattr(
            getattr(self._device, "_display_config_service", None),
            "display_brightness_min",
            None,
        )
        return float(val) if val is not None else 0.0

    @property
    @override
    def native_max_value(self) -> float:
        """Return maximum brightness from the device."""
        val = getattr(
            getattr(self._device, "_display_config_service", None),
            "display_brightness_max",
            None,
        )
        return float(val) if val is not None else 100.0

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current display brightness."""
        val = self._device.display_brightness
        return None if val is None else float(val)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the display brightness."""
        clamped = int(max(self.native_min_value, min(self.native_max_value, value)))
        await self.hass.async_add_executor_job(
            setattr, self._device, "display_brightness", clamped
        )


class SHCDisplayOnTimeNumber(SHCEntity, NumberEntity):
    """Number entity for display on-time of a TRV Gen2 or Room Thermostat 2."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_translation_key = "display_on_time"

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize the display-on-time number."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_display_on_time"

    @property
    @override
    def native_min_value(self) -> float:
        """Return minimum on-time from the device."""
        val = getattr(
            getattr(self._device, "_display_config_service", None),
            "display_on_time_min",
            None,
        )
        return float(val) if val is not None else 0.0

    @property
    @override
    def native_max_value(self) -> float:
        """Return maximum on-time from the device."""
        val = getattr(
            getattr(self._device, "_display_config_service", None),
            "display_on_time_max",
            None,
        )
        return float(val) if val is not None else 3600.0

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current display on-time in seconds."""
        val = self._device.display_on_time
        return None if val is None else float(val)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the display on-time in seconds."""
        clamped = int(max(self.native_min_value, min(self.native_max_value, value)))
        await self.hass.async_add_executor_job(
            setattr, self._device, "display_on_time", clamped
        )
