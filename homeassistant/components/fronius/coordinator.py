"""DataUpdateCoordinators for the Fronius integration."""

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, cast, override

from fronius_modbus import (
    Controls,
    FroniusModbusInverter,
    Mppt,
    Storage,
    SunSpecError,
    SunSpecMapShiftError,
)
from fronius_solarapi import (
    CommonInverterData,
    DeviceDetails,
    FroniusError,
    LoggerInfo,
    MeterData,
    OhmpilotData,
    PowerFlow,
    StorageController,
)
from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AUTO_REVERT_SECONDS,
    CONF_AUTO_REVERT_POWER_LIMIT,
    DOMAIN,
    SOLAR_NET_ID_POWER_FLOW,
    SOLAR_NET_ID_SYSTEM,
    FroniusDeviceInfo,
    SolarNetId,
)
from .entity import ModbusComponentFn, ModbusValues
from .heartbeat import LimitHeartbeat

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .solar_net import FroniusSolarNet


class FroniusCoordinatorBase[_DataT](
    ABC, DataUpdateCoordinator[dict[SolarNetId, _DataT]]
):
    """Query a Fronius endpoint.

    The data holds one `_DataT` per SolarNet device.
    """

    config_entry: FroniusConfigEntry
    default_interval: timedelta
    error_interval: timedelta
    update_exceptions: tuple[type[Exception], ...] = (FroniusError,)

    MAX_FAILED_UPDATES = 3

    def __init__(self, *args: Any, solar_net: FroniusSolarNet, **kwargs: Any) -> None:
        """Set up the FroniusCoordinatorBase class."""
        self._failed_update_count = 0
        self.solar_net = solar_net
        super().__init__(*args, update_interval=self.default_interval, **kwargs)

    @abstractmethod
    async def _update_method(self) -> dict[SolarNetId, _DataT]:
        """Return data per solar net id."""

    @override
    async def _async_update_data(self) -> dict[SolarNetId, _DataT]:
        """Fetch the latest data from the source."""
        async with self.solar_net.coordinator_lock:
            return await self._do_update()

    async def _do_update(self) -> dict[SolarNetId, _DataT]:
        """Fetch the latest data and adapt the interval to failing updates."""
        try:
            data = await self._update_method()
        except self.update_exceptions as err:
            self._failed_update_count += 1
            if self._failed_update_count == self.MAX_FAILED_UPDATES:
                self.update_interval = self.error_interval
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"fronius_error": str(err)},
            ) from err

        if self._failed_update_count != 0:
            self._failed_update_count = 0
            self.update_interval = self.default_interval
        return data

    def is_identifiable(self, device_data: _DataT) -> bool:
        """Return whether the device data carries what its entities' IDs use."""
        return True


class FroniusInverterUpdateCoordinator(FroniusCoordinatorBase[CommonInverterData]):
    """Query Fronius device inverter endpoint."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)

    def __init__(
        self, *args: Any, inverter_info: FroniusDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Fronius inverter device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info

    @override
    async def _update_method(self) -> dict[SolarNetId, CommonInverterData]:
        """Return data per solar net id."""
        # fronius-solarapi repeats requests failing with flaky Solar Net
        # communication between the logger and the inverter
        response = await self.solar_net.fronius.inverter_common_data(
            self.inverter_info.solar_net_id
        )
        return {self.inverter_info.solar_net_id: response.data}


class FroniusModbusCoordinatorBase(FroniusCoordinatorBase[ModbusValues]):
    """Shared behaviour of the coordinators reading an inverter over Modbus."""

    error_interval = timedelta(minutes=10)
    update_exceptions = (ModbusError, SunSpecError)

    def __init__(
        self,
        *args: Any,
        inverter_info: FroniusDeviceInfo,
        modbus_inverter: FroniusModbusInverter,
        **kwargs: Any,
    ) -> None:
        """Set up a Fronius Modbus device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info
        self.modbus_inverter = modbus_inverter

    @override
    async def _async_update_data(self) -> dict[SolarNetId, ModbusValues]:
        """Fetch the latest data from the source.

        The coordinator_lock rate-limits requests to the SolarAPI HTTP endpoint.
        Modbus requests use a separate transport which serializes its requests
        internally, so the lock is not needed here.
        """
        return await self._do_update()

    @abstractmethod
    async def _refresh_components(self) -> None:
        """Refresh the components this coordinator reads."""

    async def _refresh(self) -> None:
        """Refresh the components, re-discovering once on a register map shift."""
        try:
            await self._refresh_components()
        except SunSpecMapShiftError:
            # The register map shifts when the data type setting is changed on
            # the device. Re-discover once at the new addresses and retry.
            await self.modbus_inverter.discover()
            await self._refresh_components()

    def _as_device_data(self, values: ModbusValues) -> dict[SolarNetId, ModbusValues]:
        """Key the values by the solar net id of the inverter."""
        return {self.inverter_info.solar_net_id: values}


class FroniusModbusInverterUpdateCoordinator(FroniusModbusCoordinatorBase):
    """Query SunSpec MPPT data from an inverters Modbus interface."""

    default_interval = timedelta(minutes=1)

    @override
    async def _refresh_components(self) -> None:
        """Refresh the Multiple MPPT model."""
        if (mppt := self.modbus_inverter.mppt) is None:
            raise SunSpecError("Multiple MPPT model not available")
        await mppt.async_update()

    @override
    async def _update_method(self) -> dict[SolarNetId, ModbusValues]:
        """Return data per solar net id from the Modbus interface."""
        await self._refresh()
        # re-discovery on a map shift replaces the component
        mppt = cast("Mppt", self.modbus_inverter.mppt)
        values: ModbusValues = {
            "energy_total_pv": mppt.pv_energy_total,
            "storage_energy_charged_total": mppt.storage_charge_energy_total,
            "storage_energy_discharged_total": mppt.storage_discharge_energy_total,
        }
        for number, module in enumerate(mppt.modules, start=1):
            values[f"mppt_{number}_current_dc"] = module.current
            values[f"mppt_{number}_voltage_dc"] = module.voltage
            values[f"mppt_{number}_power_dc"] = module.power
            values[f"mppt_{number}_energy"] = module.energy
        return self._as_device_data(values)


class FroniusModbusSettingsUpdateCoordinator(FroniusModbusCoordinatorBase):
    """Query the writable settings of an inverters Modbus interface.

    Settings only change when something writes them, so they are polled on
    their own interval rather than with the live MPPT readings.
    """

    default_interval = timedelta(minutes=5)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up a coordinator that also writes to the device."""
        super().__init__(*args, **kwargs)
        # the heartbeat and a user's write must not interleave on the device
        self._device_lock = asyncio.Lock()
        # the fallback period to give the device, 0 for none - changing the
        # setting reloads the entry, so it is fixed for this coordinator
        self._revert_seconds = (
            AUTO_REVERT_SECONDS
            if self.config_entry.data[CONF_AUTO_REVERT_POWER_LIMIT]
            else 0
        )
        self._heartbeat = LimitHeartbeat(
            self.hass,
            self.modbus_inverter,
            device_lock=self._device_lock,
            revert_seconds=self._revert_seconds,
            logger=self.logger,
            solar_net_id=self.inverter_info.solar_net_id,
        )

    async def async_start_heartbeat(self) -> None:
        """Start keeping active limits alive, until the entry unloads."""
        self.config_entry.async_on_unload(self._heartbeat.async_stop)
        await self._heartbeat.async_start()

    @override
    async def _async_update_data(self) -> dict[SolarNetId, ModbusValues]:
        """Refresh the settings and keep the heartbeat in step with them."""
        data = await super()._async_update_data()
        self._heartbeat.async_update()
        if not self._revert_seconds:
            await self._async_clear_revert_period()
        return data

    async def _async_clear_revert_period(self) -> None:
        """Take back a period this integration left on the device.

        Only one it could have set is taken back - any other came from
        somewhere else, and dropping it would take away another controller's
        safety net. Done from the refresh so that a write that fails is
        tried again while the device holds a period it should not.
        """
        controls = self.modbus_inverter.controls
        if controls is not None and controls.revert_seconds == AUTO_REVERT_SECONDS:
            await self._heartbeat.async_resend_power_limit()
        storage = self.modbus_inverter.storage
        if storage is not None and storage.revert_seconds == AUTO_REVERT_SECONDS:
            await self._heartbeat.async_resend_battery_limits()

    @override
    async def _refresh_components(self) -> None:
        """Refresh the models carrying the writable settings."""
        for component in (
            self.modbus_inverter.controls,
            self.modbus_inverter.storage,
        ):
            if component is not None:
                await component.async_update()

    async def async_write(
        self,
        component_fn: ModbusComponentFn,
        field: str,
        value: float | bool,
        *,
        enable_field: str | None = None,
    ) -> None:
        """Write a setpoint to the device and refresh what it reports back.

        The model is refreshed first so its header check catches a shifted
        register map before anything is written - the register addresses
        move when the data type setting is changed on the device.

        A device holding a different fallback period than the configured one
        is corrected first, so an output power or battery limit the user sets
        reverts on the schedule they chose.

        ``enable_field`` names the register that puts a setpoint into effect.
        It is written again after a change, because the device only picks up a
        change to an active mode when the mode is enabled again - but only
        when the mode is already on. Turning it on is the switch's job:
        turning a limit off hands control to the next priority source, and a
        setpoint change should not quietly take it back.
        """
        component = component_fn(self.modbus_inverter)
        if component is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="modbus_model_unavailable",
            )
        try:
            async with self._device_lock:
                await component.async_update()
                if isinstance(component, Storage) and (
                    refused := _refused_battery_limits(component, field, value)
                ):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="battery_limits_conflict",
                        translation_placeholders={
                            "charge_limit": f"{refused[0]:g}",
                            "discharge_limit": f"{refused[1]:g}",
                        },
                    )
                if (
                    isinstance(component, Controls)
                    or (
                        isinstance(component, Storage) and field in BATTERY_LIMIT_FIELDS
                    )
                ) and component.revert_seconds != self._revert_seconds:
                    await component.write("revert_seconds", self._revert_seconds)
                await component.write(field, value)
                if enable_field is not None and getattr(component, enable_field):
                    await component.write(enable_field, True)
        except (ModbusError, SunSpecError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="modbus_write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        # not debounced: the entity should settle on what the device reports
        # back, and writes are rare and user initiated
        await self.async_refresh()

    @override
    async def _update_method(self) -> dict[SolarNetId, ModbusValues]:
        """Return the settings per solar net id from the Modbus interface."""
        await self._refresh()
        inverter = self.modbus_inverter
        values: ModbusValues = {}

        if (controls := inverter.controls) is not None:
            values["ac_power_limit"] = controls.power_limit
            values["ac_power_limit_enabled"] = controls.enabled
        if (storage := inverter.storage) is not None:
            values["battery_charge_power_limit"] = storage.charge_limit
            values["battery_charge_power_limit_enabled"] = storage.charge_limit_enabled
            values["battery_discharge_power_limit"] = storage.discharge_limit
            values["battery_discharge_power_limit_enabled"] = (
                storage.discharge_limit_enabled
            )
            values["battery_minimum_reserve"] = storage.minimum_reserve
            values["battery_grid_charging"] = storage.grid_charging

        return self._as_device_data(values)


BATTERY_LIMIT_FIELDS: Final = frozenset(
    {
        "charge_limit",
        "discharge_limit",
        "charge_limit_enabled",
        "discharge_limit_enabled",
    }
)


def _refused_battery_limits(
    storage: Storage, field: str, value: float | bool
) -> tuple[float, float] | None:
    """Return the charge and discharge limit a write would leave refused.

    With both limits enabled, battery power has to fit between the negated
    discharge rate and the charge rate. A Gen24 refuses an empty window -
    both rates negative, or a charge limit below a forced charging rate -
    when the second limit is enabled, and answers with a bare Modbus error.
    Other settings of the model stay writable whatever the limits are.
    """
    if field not in BATTERY_LIMIT_FIELDS:
        return None
    limits = {
        "charge_limit": storage.charge_limit,
        "discharge_limit": storage.discharge_limit,
        "charge_limit_enabled": storage.charge_limit_enabled,
        "discharge_limit_enabled": storage.discharge_limit_enabled,
        field: value,
    }
    charge, discharge = limits["charge_limit"], limits["discharge_limit"]
    if (
        limits["charge_limit_enabled"] is True
        and limits["discharge_limit_enabled"] is True
        and charge is not None
        and discharge is not None
        and charge + discharge < 0
    ):
        return charge, discharge
    return None


class FroniusLoggerUpdateCoordinator(FroniusCoordinatorBase[LoggerInfo]):
    """Query Fronius logger info endpoint."""

    default_interval = timedelta(hours=1)
    error_interval = timedelta(hours=1)

    @override
    async def _update_method(self) -> dict[SolarNetId, LoggerInfo]:
        """Return data per solar net id."""
        response = await self.solar_net.fronius.logger_info()
        return {SOLAR_NET_ID_SYSTEM: response.data}


def _has_serial(details: DeviceDetails | None) -> bool:
    """Return whether device details carry a serial number."""
    return details is not None and details.serial is not None


class FroniusMeterUpdateCoordinator(FroniusCoordinatorBase[MeterData]):
    """Query Fronius system meter endpoint."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)

    @override
    def is_identifiable(self, device_data: MeterData) -> bool:
        """Return whether the meter reports its details.

        Datamanagers before 3.3.6-14 don't report them.
        """
        return _has_serial(device_data.details)

    @override
    async def _update_method(self) -> dict[SolarNetId, MeterData]:
        """Return data per solar net id."""
        return (await self.solar_net.fronius.system_meter_data()).data


class FroniusOhmpilotUpdateCoordinator(FroniusCoordinatorBase[OhmpilotData]):
    """Query Fronius Ohmpilots."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)

    @override
    def is_identifiable(self, device_data: OhmpilotData) -> bool:
        """Return whether the Ohmpilot reports its serial number."""
        return _has_serial(device_data.details)

    @override
    async def _update_method(self) -> dict[SolarNetId, OhmpilotData]:
        """Return data per solar net id."""
        return (await self.solar_net.fronius.system_ohmpilot_data()).data


class FroniusPowerFlowUpdateCoordinator(FroniusCoordinatorBase[PowerFlow]):
    """Query Fronius power flow endpoint."""

    default_interval = timedelta(seconds=10)
    error_interval = timedelta(minutes=3)

    @override
    async def _update_method(self) -> dict[SolarNetId, PowerFlow]:
        """Return data per solar net id."""
        response = await self.solar_net.fronius.power_flow()
        return {SOLAR_NET_ID_POWER_FLOW: response.data}


class FroniusStorageUpdateCoordinator(FroniusCoordinatorBase[StorageController]):
    """Query Fronius system storage endpoint."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)

    @override
    def is_identifiable(self, device_data: StorageController) -> bool:
        """Return whether the storage reports its serial number."""
        return _has_serial(device_data.details)

    @override
    async def _update_method(self) -> dict[SolarNetId, StorageController]:
        """Return the controller data per solar net id.

        Only the controller of a storage is read - the modules are reported
        by Fronius Solar Batteries alone.
        """
        storages = (await self.solar_net.fronius.system_storage_data()).data
        return {
            solar_net_id: storage.controller
            for solar_net_id, storage in storages.items()
            if storage.controller is not None
        }
