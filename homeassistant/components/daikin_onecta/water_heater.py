"""Support for the Daikin BRP069A62."""

from collections.abc import Awaitable, Callable
from typing import Any, override

from daikin_onecta.client import DomesticHotWaterClient
from daikin_onecta.models import DomesticHotWater, Setpoint

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    WaterHeaterServiceArgument,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    management_point_unique_id,
    present_devices,
)
from .utils import round_temperature_to_step

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin water tank entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_water_tanks(coordinator, is_known),
    )


def _create_water_tanks(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinWaterTank]:
    """Create water heaters for management points with typed tank data."""
    entities: list[DaikinWaterTank] = []
    for device in present_devices(coordinator):
        supported_management_point_types = (
            "domesticHotWaterTank",
            "domesticHotWaterFlowThrough",
        )
        for management_point_type in supported_management_point_types:
            entities.extend(
                DaikinWaterTank(
                    device,
                    coordinator,
                    management_point.embedded_id,
                )
                for management_point in device.device.management_points_by_type(
                    management_point_type
                )
                if management_point.domestic_hot_water is not None
                and not is_known(
                    Platform.WATER_HEATER,
                    management_point_unique_id(device.id, management_point.embedded_id),
                )
            )
    return entities


class DaikinWaterTank(DaikinManagementPointEntity, WaterHeaterEntity):
    """Representation of a Daikin Water Tank."""

    _attr_name = None

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
    ) -> None:
        """Initialize the Water device."""
        super().__init__(device, coordinator, embedded_id)
        self._attr_unique_id = management_point_unique_id(
            self._device_id, self._embedded_id
        )
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh all state attributes from the device."""
        self._attr_supported_features = self.get_supported_features()
        self._attr_native_temperature_unit = self._get_native_temperature_unit()
        self._attr_native_current_temperature = self.get_current_temperature()
        self._attr_native_target_temperature = self.get_target_temperature()
        dht = self.domestic_hotwater_temperature
        if dht is not None and dht.min_value is not None:
            self._attr_min_temp = float(dht.min_value)
        elif hasattr(self, "_attr_min_temp"):
            del self._attr_min_temp
        if dht is not None and dht.max_value is not None:
            self._attr_max_temp = float(dht.max_value)
        elif hasattr(self, "_attr_max_temp"):
            del self._attr_max_temp
        self._attr_target_temperature_step = (
            float(dht.step_value)
            if dht is not None and dht.step_value is not None
            else 1.0
        )
        self._attr_operation_list = self.get_operation_list()
        self._attr_current_operation = self.get_current_operation()

    def _get_native_temperature_unit(self) -> UnitOfTemperature:
        """Return the Daikin temperature unit, defaulting to Celsius."""
        setpoint = self.domestic_hotwater_temperature
        unit = setpoint.unit if setpoint is not None else None
        if unit is None:
            point = self._management_point
            tank_temperature = (
                point.sensory_characteristic("tankTemperature")
                if point is not None
                else None
            )
            unit = tank_temperature.unit if tank_temperature is not None else None
        if unit is None:
            return UnitOfTemperature.CELSIUS
        try:
            return UnitOfTemperature(unit)
        except ValueError:
            return UnitOfTemperature.CELSIUS

    @property
    def _hot_water(self) -> DomesticHotWater | None:
        """Return the current typed domestic-hot-water view."""
        point = self._management_point
        return point.domestic_hot_water if point is not None else None

    @property
    @override
    def available(self) -> bool:
        """Return whether domestic-hot-water data is still available."""
        return super().available and self._hot_water is not None

    async def _async_execute_hot_water_command(
        self,
        command: Callable[[DomesticHotWaterClient], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a typed hot-water command through the cloud adapter."""
        await self._async_execute_command(
            lambda client: command(
                client.domestic_hot_water(self._device_id, self._embedded_id)
            ),
            translation_key,
        )

    @property
    def domestic_hotwater_temperature(self) -> Setpoint | None:
        """Return the domestic hot-water temperature setpoint."""
        hot_water = self._hot_water
        return hot_water.temperature if hot_water is not None else None

    def get_supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        sf = WaterHeaterEntityFeature(0)
        hot_water = self._hot_water
        if (
            hot_water is not None
            and hot_water.power is not None
            and hot_water.power.settable
        ):
            sf |= WaterHeaterEntityFeature.ON_OFF
        if self.get_operation_list():
            sf |= WaterHeaterEntityFeature.OPERATION_MODE
        # Advertise target temperature only when Daikin reports a settable
        # domestic hot-water temperature characteristic.
        dht = self.domestic_hotwater_temperature
        if dht and dht.settable:
            sf |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return sf

    def get_current_temperature(self) -> float | None:
        """Return tank temperature."""
        ret = None
        hot_water = self._hot_water
        if hot_water is not None and hot_water.current_temperature is not None:
            ret = float(hot_water.current_temperature)

        return ret

    def get_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        ret = None
        dht = self.domestic_hotwater_temperature
        if dht is not None and dht.value is not None:
            ret = float(dht.value)
        return ret

    def _validated_target_temperature(
        self, value: float, *, allow_when_off: bool = False
    ) -> float:
        """Validate and normalize a requested tank temperature."""
        hot_water = self._hot_water
        if (
            hot_water is not None
            and hot_water.power is not None
            and self.current_operation is None
        ):
            self._raise_service_validation_error("water_heater_on_off_unavailable")
        if self.current_operation == STATE_OFF and not allow_when_off:
            self._raise_service_validation_error("water_heater_off")
        dht = self.domestic_hotwater_temperature
        if dht is None or not dht.settable:
            self._raise_service_validation_error(
                "water_heater_temperature_not_settable"
            )

        step_value = dht.step_value
        return round_temperature_to_step(
            value,
            step_value,
            dht.min_value,
            dht.max_value,
            default_step=1,
            fallback_minimum=None,
            fallback_maximum=None,
        )

    async def _async_write_tank_temperature(self, target_temperature: float) -> None:
        """Write a validated target temperature if it changed."""
        if target_temperature != self._attr_native_target_temperature:
            await self._async_execute_hot_water_command(
                lambda hot_water: hot_water.set_temperature(target_temperature),
                "water_heater_set_temperature_failed",
            )
            dht = self.domestic_hotwater_temperature
            if dht is not None:
                dht.value = target_temperature
            self._publish_write_update()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        operation_mode = kwargs.get(WaterHeaterServiceArgument.OPERATION_MODE)
        temperature = kwargs.get(WaterHeaterServiceArgument.TEMPERATURE)
        target_temperature = None
        if operation_mode is not None:
            if operation_mode not in self.get_operation_list():
                self._raise_service_validation_error(
                    "water_heater_operation_mode_unavailable"
                )
            if self.current_operation is None:
                self._raise_service_validation_error("water_heater_on_off_unavailable")
        if temperature is not None:
            target_temperature = self._validated_target_temperature(
                float(temperature),
                allow_when_off=operation_mode is not None,
            )

        if operation_mode == STATE_OFF:
            if target_temperature is not None:
                await self._async_write_tank_temperature(target_temperature)
            await self.async_set_operation_mode(operation_mode)
        else:
            if operation_mode is not None:
                await self.async_set_operation_mode(operation_mode)
            if target_temperature is not None:
                await self._async_write_tank_temperature(target_temperature)

    def get_current_operation(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        hot_water = self._hot_water
        onoff = hot_water.power if hot_water is not None else None
        if onoff is None or onoff.value not in {"on", "off"}:
            return None
        if onoff.value == "off":
            return STATE_OFF
        pwf = hot_water.powerful_mode if hot_water is not None else None
        return (
            STATE_PERFORMANCE
            if pwf is not None and pwf.value == "on"
            else STATE_HEAT_PUMP
        )

    def get_operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        states: list[str] = []
        hot_water = self._hot_water
        power = hot_water.power if hot_water is not None else None
        if power is not None and power.settable:
            states = [STATE_OFF, STATE_HEAT_PUMP]
        pwf = hot_water.powerful_mode if hot_water is not None else None
        if (
            power is not None
            and (power.settable or power.value == "on")
            and pwf is not None
            and pwf.settable
        ):
            if STATE_HEAT_PUMP not in states:
                states.append(STATE_HEAT_PUMP)
            states.append(STATE_PERFORMANCE)
        return states

    def _requested_modes(self, operation_mode: str) -> tuple[str, str]:
        """Return the required on/off and powerful-mode values."""
        on_off_mode = ""
        powerful_mode = ""
        if operation_mode == STATE_OFF:
            on_off_mode = "off" if self.current_operation != STATE_OFF else ""
        elif operation_mode == STATE_PERFORMANCE:
            hot_water = self._hot_water
            power_mode = hot_water.powerful_mode if hot_water is not None else None
            if power_mode is not None and power_mode.value != "on":
                powerful_mode = "on"
            on_off_mode = "on" if self.current_operation == STATE_OFF else ""
        elif operation_mode == STATE_HEAT_PUMP:
            hot_water = self._hot_water
            power_mode = hot_water.powerful_mode if hot_water is not None else None
            if power_mode is not None and power_mode.value == "on":
                powerful_mode = "off"
            on_off_mode = "on" if self.current_operation == STATE_OFF else ""
        return on_off_mode, powerful_mode

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new tank state."""
        if operation_mode not in self.get_operation_list():
            self._raise_service_validation_error(
                "water_heater_operation_mode_unavailable"
            )
        if self.current_operation is None:
            self._raise_service_validation_error("water_heater_on_off_unavailable")
        on_off_mode, powerful_mode = self._requested_modes(operation_mode)

        if on_off_mode != "":
            await self._async_execute_hot_water_command(
                lambda hot_water: hot_water.set_power(on_off_mode == "on"),
                "water_heater_set_operation_mode_failed",
            )
            hot_water = self._hot_water
            if hot_water is not None and hot_water.power is not None:
                hot_water.power.value = on_off_mode
            self._publish_write_update()

        if powerful_mode != "" and STATE_PERFORMANCE in (self.operation_list or []):
            await self._async_execute_hot_water_command(
                lambda hot_water: hot_water.set_powerful_mode(powerful_mode == "on"),
                "water_heater_set_operation_mode_failed",
            )
            hot_water = self._hot_water
            pwf = hot_water.powerful_mode if hot_water is not None else None
            if pwf is not None and pwf.settable:
                pwf.value = powerful_mode
            self._publish_write_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn water heater on."""
        if self.current_operation is None:
            self._raise_service_validation_error("water_heater_on_off_unavailable")
        if self.current_operation == STATE_OFF:
            if not self.supported_features & WaterHeaterEntityFeature.ON_OFF:
                self._raise_service_validation_error("water_heater_on_off_unavailable")
            await self._async_execute_hot_water_command(
                lambda hot_water: hot_water.set_power(True),
                "water_heater_turn_on_failed",
            )
            hot_water = self._hot_water
            if hot_water is not None and hot_water.power is not None:
                hot_water.power.value = "on"
            self._publish_write_update()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn water heater off."""
        if self.current_operation is None:
            self._raise_service_validation_error("water_heater_on_off_unavailable")
        if self.current_operation != STATE_OFF:
            if not self.supported_features & WaterHeaterEntityFeature.ON_OFF:
                self._raise_service_validation_error("water_heater_on_off_unavailable")
            await self._async_execute_hot_water_command(
                lambda hot_water: hot_water.set_power(False),
                "water_heater_turn_off_failed",
            )
            hot_water = self._hot_water
            if hot_water is not None and hot_water.power is not None:
                hot_water.power.value = "off"
            self._publish_write_update()
