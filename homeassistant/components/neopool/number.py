"""Number platform for the NeoPool integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, override

from neopool_modbus.capabilities import (
    has_heating_relay,
    is_chlorine_module_present,
    is_hydrolysis_present,
    is_ph_module_present,
    is_redox_module_present,
    is_temperature_active,
)
from neopool_modbus.decoders import decode_masked_flag, is_hydrolysis_in_percent
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import MaskedFlag, SetpointKind, is_valid_relay_gpio

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_USE_COVER_SENSOR
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Wait for the stepper to settle so only the final value hits the device's EEPROM.
WRITE_DELAY = timedelta(seconds=3)


@dataclass(frozen=True, kw_only=True)
class NeoPoolNumberEntityDescription(NumberEntityDescription):
    """Describes a NeoPool number entity.

    Exactly one write target must be set:

    - ``setpoint``: write via ``client.async_set_setpoint(kind, value)``
    - ``masked_flag``: write via ``client.async_set_masked_register(flag, value)``
    """

    setpoint: SetpointKind | None = None
    masked_flag: MaskedFlag | None = None
    data_key: str | None = None
    scale: float = 1.0
    supported_fn: Callable[[dict[str, Any]], bool] | None = None
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None
    max_fn: Callable[[dict[str, Any]], float | None] | None = None
    step_fn: Callable[[dict[str, Any]], float | None] | None = None


def _support_heating_temp(data: dict[str, Any]) -> bool:
    return has_heating_relay(data) and is_temperature_active(data)


def _support_ph_max(data: dict[str, Any]) -> bool:
    """Require a pH module and a valid acid relay GPIO (or none reported)."""
    return is_ph_module_present(data) and (
        "MBF_PAR_PH_ACID_RELAY_GPIO" not in data
        or is_valid_relay_gpio(data["MBF_PAR_PH_ACID_RELAY_GPIO"] or 0)
    )


def _support_ph_min(data: dict[str, Any]) -> bool:
    """Require a pH module and a valid base relay GPIO (or none reported)."""
    return is_ph_module_present(data) and (
        "MBF_PAR_PH_BASE_RELAY_GPIO" not in data
        or is_valid_relay_gpio(data["MBF_PAR_PH_BASE_RELAY_GPIO"] or 0)
    )


def _hidro_unit(data: dict[str, Any]) -> str:
    """Surface the hydrolysis target unit dynamically: % or g/h."""
    return PERCENTAGE if is_hydrolysis_in_percent(data) else "g/h"


def _hidro_max(data: dict[str, Any]) -> float | None:
    """Use the device-reported nominal as the hidro maximum, or fall back to the static default."""
    hidro_nom = data.get("MBF_PAR_HIDRO_NOM")
    return float(hidro_nom) if hidro_nom is not None else None


def _hidro_step(data: dict[str, Any]) -> float:
    """Step is 1 in percent mode, 0.1 in g/h mode."""
    return 1.0 if is_hydrolysis_in_percent(data) else 0.1


NUMBER_DESCRIPTIONS: dict[str, NeoPoolNumberEntityDescription] = {
    "MBF_PAR_HIDRO": NeoPoolNumberEntityDescription(
        key="MBF_PAR_HIDRO",
        translation_key="hidro",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        setpoint=SetpointKind.HIDRO,
        scale=10.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_hydrolysis_present,
        unit_fn=_hidro_unit,
        max_fn=_hidro_max,
        step_fn=_hidro_step,
    ),
    "MBF_PAR_PH1": NeoPoolNumberEntityDescription(
        key="MBF_PAR_PH1",
        translation_key="ph1",
        device_class=NumberDeviceClass.PH,
        native_min_value=0.0,
        native_max_value=14.0,
        native_step=0.1,
        setpoint=SetpointKind.PH_MAX,
        scale=100.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=_support_ph_max,
    ),
    "MBF_PAR_PH2": NeoPoolNumberEntityDescription(
        key="MBF_PAR_PH2",
        translation_key="ph2",
        device_class=NumberDeviceClass.PH,
        native_min_value=0.0,
        native_max_value=14.0,
        native_step=0.1,
        setpoint=SetpointKind.PH_MIN,
        scale=100.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=_support_ph_min,
    ),
    "MBF_PAR_RX1": NeoPoolNumberEntityDescription(
        key="MBF_PAR_RX1",
        translation_key="rx1",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        native_min_value=0.0,
        native_max_value=1000.0,
        native_step=1.0,
        setpoint=SetpointKind.REDOX,
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_redox_module_present,
    ),
    "MBF_PAR_CL1": NeoPoolNumberEntityDescription(
        key="MBF_PAR_CL1",
        translation_key="cl1",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        native_min_value=0.0,
        native_max_value=10.0,
        native_step=0.1,
        setpoint=SetpointKind.CHLORINE,
        scale=100.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_chlorine_module_present,
    ),
    "MBF_PAR_HEATING_TEMP": NeoPoolNumberEntityDescription(
        key="MBF_PAR_HEATING_TEMP",
        translation_key="heating_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=0.0,
        native_max_value=40.0,
        native_step=1.0,
        setpoint=SetpointKind.HEATING,
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=_support_heating_temp,
    ),
    "MBF_PAR_SMART_TEMP_HIGH": NeoPoolNumberEntityDescription(
        key="MBF_PAR_SMART_TEMP_HIGH",
        translation_key="smart_temp_high",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=0.0,
        native_max_value=40.0,
        native_step=1.0,
        setpoint=SetpointKind.SMART_TEMP_HIGH,
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_temperature_active,
    ),
    "MBF_PAR_SMART_TEMP_LOW": NeoPoolNumberEntityDescription(
        key="MBF_PAR_SMART_TEMP_LOW",
        translation_key="smart_temp_low",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=0.0,
        native_max_value=40.0,
        native_step=1.0,
        setpoint=SetpointKind.SMART_TEMP_LOW,
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_temperature_active,
    ),
    "MBF_PAR_HIDRO_COVER_REDUCTION": NeoPoolNumberEntityDescription(
        key="MBF_PAR_HIDRO_COVER_REDUCTION",
        translation_key="hidro_cover_reduction",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        masked_flag=MaskedFlag.HIDRO_COVER_REDUCTION_PERCENT,
        data_key="MBF_PAR_HIDRO_COVER_REDUCTION",
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=is_hydrolysis_present,
    ),
    "MBF_PAR_HIDRO_SHUTDOWN_TEMPERATURE": NeoPoolNumberEntityDescription(
        key="MBF_PAR_HIDRO_SHUTDOWN_TEMPERATURE",
        translation_key="hidro_shutdown_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=1.0,
        native_max_value=40.0,
        native_step=1.0,
        masked_flag=MaskedFlag.HIDRO_SHUTDOWN_TEMPERATURE,
        data_key="MBF_PAR_HIDRO_COVER_REDUCTION",
        scale=1.0,
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda data: (
            is_hydrolysis_present(data) and is_temperature_active(data)
        ),
    ),
}


# Entities gated on a config-entry option (in addition to their supported_fn).
_ENTITY_OPTION_KEY: dict[str, str] = {
    "MBF_PAR_HIDRO_COVER_REDUCTION": CONF_USE_COVER_SENSOR,
    "MBF_PAR_HIDRO_SHUTDOWN_TEMPERATURE": CONF_USE_COVER_SENSOR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool number entities from a config entry."""
    coordinator = entry.runtime_data
    options = entry.options

    async_add_entities(
        NeoPoolNumber(coordinator, key, desc)
        for key, desc in NUMBER_DESCRIPTIONS.items()
        if (
            (option_key := _ENTITY_OPTION_KEY.get(key)) is None
            or bool(options.get(option_key))
        )
        and (desc.supported_fn is None or desc.supported_fn(coordinator.data))
    )


class NeoPoolNumber(NeoPoolEntity, NumberEntity):
    """Representation of a NeoPool number entity."""

    entity_description: NeoPoolNumberEntityDescription
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolNumberEntityDescription,
    ) -> None:
        """Initialize the NeoPool number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._data_key = description.data_key or key
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

        self._write_unsub: CALLBACK_TYPE | None = None
        self._pending_value: float | None = None
        self._removing = False

    def _decode_raw(self) -> float | None:
        """Decode the current coordinator-data value for this entity."""
        if (flag := self.entity_description.masked_flag) is not None:
            return decode_masked_flag(flag, self.coordinator.data)
        raw = self.coordinator.data.get(self._data_key)
        return raw if isinstance(raw, (int, float)) else None

    @override
    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to hass."""
        await super().async_added_to_hass()

        val = self._decode_raw()
        self._attr_native_value = float(val) if isinstance(val, (int, float)) else None

        self.async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending write when removed."""
        self._removing = True
        self._cancel_pending_write()
        await super().async_will_remove_from_hass()

    @callback
    def _cancel_pending_write(self) -> None:
        """Cancel a scheduled write, if any."""
        if self._write_unsub is not None:
            self._write_unsub()
            self._write_unsub = None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the number entity."""
        self._pending_value = value
        # Show the pending value optimistically. Write happens once the stepper
        # settles; restart the timer so it fires after the last click, not the
        # first, sparing the device a flash cycle per intermediate step.
        self.async_write_ha_state()
        self._cancel_pending_write()
        self._write_unsub = async_call_later(
            self.hass, WRITE_DELAY, self._async_write_pending
        )

    async def _async_write_pending(self, _now: datetime) -> None:
        """Write the pending value via the appropriate lib high-level API."""
        self._write_unsub = None
        if (pending := self._pending_value) is None:  # pragma: no cover
            # Defensive: the timer only fires after a value is queued.
            return
        self._pending_value = None
        client = self.coordinator.client
        desc = self.entity_description
        raw = round(pending * desc.scale)
        # No EEPROM cycle if the settled value already matches the device.
        if (current := self._decode_raw()) is not None and (
            round(current * desc.scale) == raw
        ):
            return
        try:
            if desc.setpoint is not None:
                await client.async_set_setpoint(desc.setpoint, raw)
                # Merge the quantized value the device stored, not the raw input.
                overrides = {self._data_key: raw / desc.scale}
            elif desc.masked_flag is not None:
                # Serialize the read-modify-write against sibling writes.
                async with self.coordinator.masked_write_lock:
                    overrides = await client.async_set_masked_register(
                        desc.masked_flag, raw
                    )
            else:  # pragma: no cover - description validated upstream
                return
        except (NeoPoolError, OSError, TimeoutError) as err:
            # Background write: log and drop; the next poll restores state.
            _LOGGER.warning("Failed to write %s: %s", self.entity_description.key, err)
            return
        if self._removing:
            # Removed mid-write: the client may be closing, leave the coordinator alone.
            return
        self.coordinator.async_set_updated_data({**self.coordinator.data, **overrides})
        self.coordinator.request_refresh_with_followup()

    @property
    @override
    def native_value(self) -> float | None:
        """Return the actual number value."""
        # While a debounced write is pending, surface the requested value so the
        # UI reflects it optimistically instead of the stale coordinator value.
        if self._pending_value is not None:
            return self._pending_value
        raw = self._decode_raw()
        if raw is None:
            return self._attr_native_value
        return float(raw)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the number value."""
        if (unit_fn := self.entity_description.unit_fn) is not None:
            return unit_fn(self.coordinator.data)
        return self.entity_description.native_unit_of_measurement

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value for the number entity."""
        if (max_fn := self.entity_description.max_fn) is not None:
            if (dynamic_max := max_fn(self.coordinator.data)) is not None:
                return dynamic_max
        return self.entity_description.native_max_value or super().native_max_value

    @property
    @override
    def native_step(self) -> float | None:
        """Return the step value for the number entity."""
        if (step_fn := self.entity_description.step_fn) is not None:
            return step_fn(self.coordinator.data)
        return self.entity_description.native_step
