"""Number platform for the NeoPool integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_USE_COVER_SENSOR, DOMAIN
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

# The platform coalesces rapid writes per entity via a debounce timer and
# serializes the shared masked register with masked_write_lock, so a platform
# semaphore would add nothing but latency between independent UI interactions.
PARALLEL_UPDATES = 0

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
        self._write_future: asyncio.Future[None] | None = None
        self._flush_lock = asyncio.Lock()
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
        if self._write_future is not None and not self._write_future.done():
            # Wake any awaiting callers; they treat cancellation as a clean exit.
            self._write_future.cancel()
        await super().async_will_remove_from_hass()

    @callback
    def _cancel_pending_write(self) -> None:
        """Cancel a scheduled write, if any."""
        if self._write_unsub is not None:
            self._write_unsub()
            self._write_unsub = None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the number entity.

        The write is debounced so a rapid stepper settles into a single EEPROM
        cycle. Every caller in the same debounce window awaits one shared future
        that the coalesced write resolves, so a blocking service call still sees
        the write's outcome and surfaces any device error.
        """
        self._pending_value = value
        # Show the pending value optimistically. Write happens once the stepper
        # settles; restart the timer so it fires after the last click, not the
        # first, sparing the device a flash cycle per intermediate step.
        self.async_write_ha_state()
        self._cancel_pending_write()
        if self._write_future is None or self._write_future.done():
            self._write_future = self.hass.loop.create_future()
        future = self._write_future
        self._write_unsub = async_call_later(self.hass, WRITE_DELAY, self._async_flush)
        try:
            # Shield the shared future: cancelling one caller's service task must
            # not cancel the batch and release the other coalesced callers.
            await asyncio.shield(future)
        except asyncio.CancelledError:
            if self._removing:
                # Removed while waiting: nothing to report, exit cleanly.
                return
            # This service task was cancelled, not the batch: re-raise so the
            # caller's cancellation propagates while the shielded future lives on.
            raise

    async def _async_flush(self, _now: datetime) -> None:
        """Write the settled value, resolving the awaited coalesce future."""
        self._write_unsub = None
        # Detach this batch: a set_value arriving during the write below must
        # start a fresh future and its own flush, not reuse or resolve this one.
        future = self._write_future
        self._write_future = None
        # Snapshot the queued value for this batch. Leave _pending_value in
        # place: a later set_value may already have replaced it, and it backs
        # the optimistic native_value the UI shows until this write commits.
        pending = self._pending_value
        # Only a run that reaches the end reports success; any earlier exit
        # (device error, cancel, an unexpected raise) resolves the future
        # itself or leaves it for the finally to fail, never a false success.
        resolved = False
        try:
            if pending is None:  # pragma: no cover
                # Defensive: the timer only fires after a value is queued.
                return
            # Serialize flushes so a later batch cannot overlap this write and
            # resolve out of order.
            async with self._flush_lock:
                client = self.coordinator.client
                desc = self.entity_description
                raw = round(pending * desc.scale)
                # No EEPROM cycle if the settled value already matches the device.
                if (current := self._decode_raw()) is not None and (
                    round(current * desc.scale) == raw
                ):
                    # Settled value already on the device: no write, but the
                    # caller succeeded. Drop the optimistic value back to the
                    # register reading and resolve the batch.
                    self._clear_pending_if_current(pending)
                    if future is not None and not future.done():
                        future.set_result(None)
                    resolved = True
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
                    # Roll the optimistic value back to the register reading and
                    # report the failure to the awaiting caller.
                    self._report_write_failure(future, pending, err)
                    resolved = True
                    return
                except Exception as err:  # noqa: BLE001
                    # An unexpected write error must still reach the blocking
                    # caller as a failure, never resolve as a silent success.
                    self._report_write_failure(future, pending, err)
                    resolved = True
                    return
                if self._removing:
                    # Removed mid-write: the client may be closing, leave the
                    # coordinator alone. The caller treats cancellation as a
                    # clean exit, so release its future that way; _write_future
                    # is already detached, so removal cannot cancel it for us.
                    if future is not None and not future.done():
                        future.cancel()
                    resolved = True
                    return
                try:
                    # Merge the device result first, then drop the optimistic
                    # value: clearing it before the merge would briefly surface
                    # the stale register reading and emit a rollback state event.
                    self.coordinator.async_set_updated_data(
                        {**self.coordinator.data, **overrides}
                    )
                    self._clear_pending_if_current(pending)
                    self.coordinator.request_refresh_with_followup()
                except Exception as err:  # noqa: BLE001
                    # A merge/refresh error after the device write must reach the
                    # caller as a failure, not fall through to a success result.
                    self._report_write_failure(future, pending, err)
                    resolved = True
                    return
                if future is not None and not future.done():
                    future.set_result(None)
                resolved = True
        finally:
            # A bare cancel of this flush task leaves resolved False: fail the
            # batch rather than letting a blocking caller read a false success.
            if not resolved and future is not None and not future.done():
                future.cancel()  # pragma: no cover - task cancel is non-deterministic

    @callback
    def _report_write_failure(
        self,
        future: asyncio.Future[None] | None,
        batch_value: float,
        err: Exception,
    ) -> None:
        """Roll the optimistic value back and fail the awaiting caller."""
        self._clear_pending_if_current(batch_value)
        if future is not None and not future.done():
            future.set_exception(
                HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="modbus_communication_error",
                    translation_placeholders={"error": str(err)},
                )
            )

    @callback
    def _clear_pending_if_current(self, batch_value: float) -> None:
        """Drop the optimistic value unless a newer write already replaced it.

        A later set_value during this batch's device I/O leaves its own value in
        _pending_value; clearing it then would flash the stale register reading
        until that newer write commits, so only this batch's value is cleared.
        """
        if self._pending_value == batch_value:
            self._pending_value = None
        self.async_write_ha_state()

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
