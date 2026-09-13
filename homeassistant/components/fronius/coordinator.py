"""DataUpdateCoordinators for the Fronius integration."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast, override

from fronius_modbus import (
    FroniusModbusInverter,
    Mppt,
    SunSpecError,
    SunSpecMapShiftError,
)
from modbus_connection import ModbusError
from pyfronius import BadStatusError, FroniusError

from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .binary_sensor import POWER_FLOW_BINARY_SENSOR_DESCRIPTIONS
from .const import (
    DOMAIN,
    SOLAR_NET_ID_POWER_FLOW,
    SOLAR_NET_ID_SYSTEM,
    FroniusDeviceInfo,
    SolarNetId,
)
from .entity import FroniusEntity, FroniusEntityDescription, ModbusComponentFn
from .number import MODBUS_NUMBER_ENTITY_DESCRIPTIONS
from .sensor import (
    INVERTER_ENTITY_DESCRIPTIONS,
    LOGGER_ENTITY_DESCRIPTIONS,
    METER_ENTITY_DESCRIPTIONS,
    MODBUS_INVERTER_ENTITY_DESCRIPTIONS,
    OHMPILOT_ENTITY_DESCRIPTIONS,
    POWER_FLOW_ENTITY_DESCRIPTIONS,
    STORAGE_ENTITY_DESCRIPTIONS,
)
from .switch import MODBUS_SWITCH_ENTITY_DESCRIPTIONS

if TYPE_CHECKING:
    from . import FroniusConfigEntry, FroniusSolarNet


class FroniusCoordinatorBase(
    ABC, DataUpdateCoordinator[dict[SolarNetId, dict[str, Any]]]
):
    """Query Fronius endpoint and keep track of seen conditions."""

    config_entry: FroniusConfigEntry
    default_interval: timedelta
    error_interval: timedelta
    valid_descriptions: Mapping[Platform, Sequence[FroniusEntityDescription]]
    update_exceptions: tuple[type[Exception], ...] = (FroniusError,)

    MAX_FAILED_UPDATES = 3

    def __init__(self, *args: Any, solar_net: FroniusSolarNet, **kwargs: Any) -> None:
        """Set up the FroniusCoordinatorBase class."""
        self._failed_update_count = 0
        self.solar_net = solar_net
        # unregistered_descriptors are used to create entities in platform module
        self.unregistered_descriptors: dict[
            SolarNetId, dict[Platform, list[FroniusEntityDescription]]
        ] = {}
        super().__init__(*args, update_interval=self.default_interval, **kwargs)

    @abstractmethod
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""

    @override
    async def _async_update_data(self) -> dict[SolarNetId, Any]:
        """Fetch the latest data from the source."""
        async with self.solar_net.coordinator_lock:
            return await self._do_update()

    async def _do_update(self) -> dict[SolarNetId, Any]:
        """Fetch the latest data and keep track of seen conditions."""
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

        for solar_net_id in data:
            if solar_net_id not in self.unregistered_descriptors:
                # id seen for the first time
                self.unregistered_descriptors[solar_net_id] = {
                    platform: list(descriptions)
                    for platform, descriptions in self.valid_descriptions.items()
                }
        return data

    @callback
    def add_entities_for_seen_keys[_FroniusEntityT: FroniusEntity](
        self,
        async_add_entities: AddEntitiesCallback,
        platform: Platform,
        entity_constructor: type[_FroniusEntityT],
    ) -> None:
        """Add entities for received keys and registers listener for future seen keys.

        Called from a platforms `async_setup_entry`.
        """

        @callback
        def _add_entities_for_unregistered_descriptors() -> None:
            """Add entities for keys seen for the first time."""
            new_entities: list[_FroniusEntityT] = []
            for solar_net_id, device_data in self.data.items():
                remaining_unregistered_descriptors = []
                for description in self.unregistered_descriptors[solar_net_id][
                    platform
                ]:
                    key = description.response_key or description.key
                    if key not in device_data:
                        remaining_unregistered_descriptors.append(description)
                        continue
                    if device_data[key]["value"] is None:
                        remaining_unregistered_descriptors.append(description)
                        continue
                    new_entities.append(
                        entity_constructor(
                            coordinator=self,
                            description=description,
                            solar_net_id=solar_net_id,
                        )
                    )
                self.unregistered_descriptors[solar_net_id][platform] = (
                    remaining_unregistered_descriptors
                )
            async_add_entities(new_entities)

        _add_entities_for_unregistered_descriptors()
        self.solar_net.config_entry.async_on_unload(
            self.async_add_listener(_add_entities_for_unregistered_descriptors)
        )


class FroniusInverterUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius device inverter endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = {Platform.SENSOR: INVERTER_ENTITY_DESCRIPTIONS}

    SILENT_RETRIES = 3

    def __init__(
        self, *args: Any, inverter_info: FroniusDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Fronius inverter device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        # almost 1% of `current_inverter_data` requests on Symo devices result in
        # `BadStatusError Code: 8 - LNRequestTimeout` due to flaky internal
        # communication between the logger and the inverter.
        for silent_retry in range(self.SILENT_RETRIES):
            try:
                data = await self.solar_net.fronius.current_inverter_data(
                    self.inverter_info.solar_net_id
                )
            except BadStatusError:
                if silent_retry == (self.SILENT_RETRIES - 1):
                    raise
                continue
            break
        # wrap a single devices data in a dict with solar_net_id key for
        # FroniusCoordinatorBase _async_update_data and add_entities_for_seen_keys
        return {self.inverter_info.solar_net_id: data}


class FroniusModbusCoordinatorBase(FroniusCoordinatorBase):
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
    async def _async_update_data(self) -> dict[SolarNetId, Any]:
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

    def _as_device_data(
        self, values: Mapping[str, float | bool | None]
    ) -> dict[SolarNetId, Any]:
        """Wrap values in the SolarAPI's {"value": ...} shape entities read."""
        return {
            self.inverter_info.solar_net_id: {
                key: {"value": value} for key, value in values.items()
            }
        }


class FroniusModbusInverterUpdateCoordinator(FroniusModbusCoordinatorBase):
    """Query SunSpec MPPT data from an inverters Modbus interface."""

    default_interval = timedelta(minutes=1)
    valid_descriptions = {Platform.SENSOR: MODBUS_INVERTER_ENTITY_DESCRIPTIONS}

    @override
    async def _refresh_components(self) -> None:
        """Refresh the Multiple MPPT model."""
        if (mppt := self.modbus_inverter.mppt) is None:
            raise SunSpecError("Multiple MPPT model not available")
        await mppt.async_update()

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from the Modbus interface."""
        await self._refresh()
        # re-discovery on a map shift replaces the component
        mppt = cast("Mppt", self.modbus_inverter.mppt)
        values: dict[str, float | bool | None] = {
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
    valid_descriptions = {
        Platform.NUMBER: MODBUS_NUMBER_ENTITY_DESCRIPTIONS,
        Platform.SWITCH: MODBUS_SWITCH_ENTITY_DESCRIPTIONS,
    }

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
            await component.async_update()
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
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return the settings per solar net id from the Modbus interface."""
        await self._refresh()
        inverter = self.modbus_inverter
        values: dict[str, float | bool | None] = {}

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


class FroniusLoggerUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius logger info endpoint and keep track of seen conditions."""

    default_interval = timedelta(hours=1)
    error_interval = timedelta(hours=1)
    valid_descriptions = {Platform.SENSOR: LOGGER_ENTITY_DESCRIPTIONS}

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_logger_info()
        return {SOLAR_NET_ID_SYSTEM: data}


class FroniusMeterUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius system meter endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = {Platform.SENSOR: METER_ENTITY_DESCRIPTIONS}

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_meter_data()
        return data["meters"]  # type: ignore[no-any-return]


class FroniusOhmpilotUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius Ohmpilots and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = {Platform.SENSOR: OHMPILOT_ENTITY_DESCRIPTIONS}

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_ohmpilot_data()
        return data["ohmpilots"]  # type: ignore[no-any-return]


class FroniusPowerFlowUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius power flow endpoint and keep track of seen conditions."""

    default_interval = timedelta(seconds=10)
    error_interval = timedelta(minutes=3)
    valid_descriptions = {
        Platform.SENSOR: POWER_FLOW_ENTITY_DESCRIPTIONS,
        Platform.BINARY_SENSOR: POWER_FLOW_BINARY_SENSOR_DESCRIPTIONS,
    }

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_power_flow()
        return {SOLAR_NET_ID_POWER_FLOW: data}


class FroniusStorageUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius system storage endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = {Platform.SENSOR: STORAGE_ENTITY_DESCRIPTIONS}

    @override
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_storage_data()
        return data["storages"]  # type: ignore[no-any-return]
