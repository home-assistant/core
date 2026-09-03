"""Contains sensors exposed by the Prism wallbox integration."""

from contextlib import suppress
from decimal import Decimal
import logging
from typing import override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import SENSOR_DOMAIN
from .entity import PrismBaseEntity, _get_unique_id
from .entry_data import RuntimeEntryData
from .solar_balance import (
    SOLAR_BALANCE_CHARGING_SURPLUS,
    SOLAR_BALANCE_DISABLED,
    SOLAR_BALANCE_EXTERNAL_PAUSED,
    SOLAR_BALANCE_LOW_SURPLUS_KEEP_CHARGING,
    SOLAR_BALANCE_PAUSED_LOW_SURPLUS,
    SOLAR_BALANCE_WAITING_BATTERY_DATA,
    SOLAR_BALANCE_WAITING_DATA,
    SOLAR_BALANCE_WAITING_SOLAR_MODE,
    SOLAR_BALANCE_WAITING_STABLE_SURPLUS,
    SolarBalanceState,
    get_solar_balance_signal,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all sensors for this entry."""
    entry_data: RuntimeEntryData = entry.runtime_data
    _LOGGER.debug("async_setup_entry for sensors: %s", entry_data)
    ports = entry_data.ports

    sensors: list[SensorEntity] = []
    for port in range(1, ports + 1):
        sensors.extend(
            [PrismSensor(entry_data, description, port) for description in SENSORS]
        )
    sensors.extend(
        [PrismSensor(entry_data, description, 0) for description in BASE_SENSORS]
    )
    if entry_data.powerwall:
        sensors.extend(
            [
                PrismSensor(entry_data, description, 0)
                for description in POWERWALL_SENSORS
            ]
        )
    if entry_data.vsensors:
        sensors.append(PrismGridEnergy(entry_data, VSENSORS[0]))
    if entry_data.solar_battery_balance:
        for port in range(1, ports + 1):
            entry_data.solar_balance_states.setdefault(port, SolarBalanceState())
            sensors.extend(
                [
                    PrismSolarBalanceSensor(entry_data, description, port)
                    for description in SOLAR_BALANCE_SENSORS
                ]
            )
    async_add_entities(sensors)


class PrismSensorEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """A class that describes prism binary sensor entities."""

    expire_after: float = 600
    topic: str | None = None


class PrismSolarBalanceSensorEntityDescription(
    SensorEntityDescription, frozen_or_thawed=True
):
    """A class that describes Prism solar balance sensors."""

    value_key: str | None = None


class PrismGridEnergy(RestoreSensor):
    """A Sensor that compute the integral of energy take from grid."""

    _attr_has_entity_name = True

    _attr_should_poll = False
    _attr_translation_key = "input_grid_energy"

    def __init__(
        self, entry_data: RuntimeEntryData, description: SensorEntityDescription
    ) -> None:
        """Init Prism energy sensor."""
        self._attr_device_info = entry_data.devices[0]
        self.entity_description = description
        self._attr_unique_id = _get_unique_id(entry_data.serial, description.key)
        self._integral: Decimal = Decimal(0)

    @override
    async def async_added_to_hass(self) -> None:
        """Sensor is added to hass."""
        _LOGGER.debug("async_added_to_hass %s", self.entity_description.key)
        await super().async_added_to_hass()

        if state := await self.async_get_last_state():
            _LOGGER.debug("async_added_to_hass last state %s", state)
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                with suppress(ValueError):
                    self._integral = Decimal(state.state)
                    self._attr_native_value = round(self._integral, 1)
            else:
                _LOGGER.warning(
                    "Can't restore state of %s",
                    self.entity_description.key,
                )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, "sensor.silla_prism_input_grid_power", self._calc_integral
            )
        )

    @callback
    def _calc_integral(self, event: Event[EventStateChangedData]) -> None:
        """Handle the sensor state changes."""
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        if old_state is None or new_state is None:
            return

        if old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE) or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            if self._attr_available:
                self._attr_available = False
                self.async_write_ha_state()
            return

        elapsed_time = Decimal(
            ((new_state.last_updated - old_state.last_updated).total_seconds()) / 3600
        )

        # Wh to kWh conversion is Wh/1000
        average_value = (Decimal(new_state.state) + Decimal(old_state.state)) / Decimal(
            2000
        )

        self._integral += elapsed_time * average_value

        # _LOGGER.debug(
        #     "Elapsed_time: %s, average_value: %s, integral: %s",
        #     elapsed_time,
        #     average_value,
        #     self._integral,
        # )

        self._attr_native_value = round(self._integral, 1)

        if not self._attr_available:
            self._attr_available = True
        self.async_write_ha_state()


class PrismSensor(PrismBaseEntity, SensorEntity):
    """A Sensor for Prism EVSE devices."""

    _attr_has_entity_name = True

    entity_description: PrismSensorEntityDescription

    def _get_description(
        self, port: int, mulitport: bool, description: PrismSensorEntityDescription
    ) -> PrismSensorEntityDescription:
        if port == 0:
            return description
        assert description.topic is not None
        if mulitport:
            return PrismSensorEntityDescription(
                key=description.key.format(port),
                topic=description.topic.format(port),
                device_class=description.device_class,
                state_class=description.state_class,
                native_unit_of_measurement=description.native_unit_of_measurement,
                suggested_display_precision=description.suggested_display_precision,
                options=description.options,
                has_entity_name=description.has_entity_name,
                translation_key=description.translation_key,
            )
        return PrismSensorEntityDescription(
            key=description.key[:-3],
            topic=description.topic.format(port),
            device_class=description.device_class,
            state_class=description.state_class,
            native_unit_of_measurement=description.native_unit_of_measurement,
            suggested_display_precision=description.suggested_display_precision,
            options=description.options,
            has_entity_name=description.has_entity_name,
            translation_key=description.translation_key,
        )

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismSensorEntityDescription,
        port: int,
    ) -> None:
        """Init Prism sensor."""
        ismultiport = entry_data.ports > 1
        if not ismultiport:
            device = entry_data.devices[0]
        else:
            device = entry_data.devices[port]
        super().__init__(
            entry_data,
            SENSOR_DOMAIN,
            self._get_description(port, ismultiport, description),
            device,
        )

    @override
    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self.schedule_expiration_callback()
        # Update native value
        if self.options is not None:
            try:
                self._attr_native_value = self.options[int(msg.payload) - 1]
            except IndexError:
                self._attr_native_value = None
        else:
            self._attr_native_value = msg.payload
        # Schedule update ha state
        self.schedule_update_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        # _LOGGER.debug("async_added_to_hass")
        self._attr_available = False
        await self._subscribe_topic()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove entity from hass."""
        _LOGGER.debug("called async_will_remove_from_hass fir %s", self.entity_id)
        await super().async_will_remove_from_hass()
        # Clean up expire triggers
        if self._expiration_trigger:
            self._expiration_trigger()
            self._expiration_trigger = None
            self._attr_available = True


class PrismSolarBalanceSensor(SensorEntity):
    """Expose the latest solar battery balance calculation."""

    _attr_has_entity_name = True

    entity_description: PrismSolarBalanceSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismSolarBalanceSensorEntityDescription,
        port: int,
    ) -> None:
        """Initialize Prism solar balance sensor."""
        self._entry_data = entry_data
        self._port = port
        self.entity_description = self._get_description(
            port, entry_data.ports > 1, description
        )
        if entry_data.ports > 1:
            self._attr_device_info = entry_data.devices[port]
        else:
            self._attr_device_info = entry_data.devices[0]
        self._attr_unique_id = _get_unique_id(
            entry_data.serial, self.entity_description.key
        )
        self._balance_state = entry_data.solar_balance_states.setdefault(
            port, SolarBalanceState()
        )
        self._apply_balance_state(self._balance_state)

    def _get_description(
        self,
        port: int,
        multiport: bool,
        description: PrismSolarBalanceSensorEntityDescription,
    ) -> PrismSolarBalanceSensorEntityDescription:
        if multiport:
            key = description.key.format(port)
        else:
            key = description.key[:-3]
        return PrismSolarBalanceSensorEntityDescription(
            key=key,
            device_class=description.device_class,
            state_class=description.state_class,
            native_unit_of_measurement=description.native_unit_of_measurement,
            suggested_display_precision=description.suggested_display_precision,
            options=description.options,
            has_entity_name=description.has_entity_name,
            translation_key=description.translation_key,
            value_key=description.value_key,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Listen for solar balance updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                get_solar_balance_signal(self._entry_data.serial, self._port),
                self._balance_state_updated,
            )
        )

    @callback
    def _balance_state_updated(self, state: SolarBalanceState) -> None:
        """Handle a solar balance state update."""
        self._balance_state = state
        self._apply_balance_state(state)
        self.async_write_ha_state()

    def _apply_balance_state(self, state: SolarBalanceState) -> None:
        if self.entity_description.value_key == "status":
            self._attr_native_value = state.status
        elif self.entity_description.value_key == "surplus_current":
            self._attr_native_value = state.surplus_current
        elif self.entity_description.value_key == "start_delay_remaining":
            self._attr_native_value = state.start_delay_remaining or 0
        elif self.entity_description.value_key == "available_power":
            self._attr_native_value = state.available_power
        elif self.entity_description.value_key == "battery_power_used":
            self._attr_native_value = state.battery_power_used
        elif self.entity_description.value_key == "grid_power":
            self._attr_native_value = state.grid_power
        elif self.entity_description.value_key == "solar_power":
            self._attr_native_value = state.solar_power
        elif self.entity_description.value_key == "home_load_power":
            self._attr_native_value = state.home_load_power
        elif self.entity_description.value_key == "target_current":
            self._attr_native_value = state.target_current
        elif self.entity_description.value_key == "raw_target_current":
            self._attr_native_value = state.raw_target_current
        elif self.entity_description.value_key == "theoretical_target_current":
            self._attr_native_value = state.theoretical_target_current
        elif self.entity_description.value_key == "battery_reserve_power":
            self._attr_native_value = state.battery_reserve_power
        elif self.entity_description.value_key == "battery_reserve_shortfall_power":
            self._attr_native_value = state.battery_reserve_shortfall_power
        elif self.entity_description.value_key == "target_export_power":
            self._attr_native_value = state.target_export_power
        elif self.entity_description.value_key == "unused_export_power":
            self._attr_native_value = state.unused_export_power
        elif self.entity_description.value_key == "residual_export_remaining":
            self._attr_native_value = state.residual_export_remaining or 0
        elif self.entity_description.value_key == "decision_reason":
            self._attr_native_value = state.decision_reason
        elif self.entity_description.value_key == "decision_summary":
            self._attr_native_value = state.decision_summary

        self._attr_extra_state_attributes = {
            "decision_summary": state.decision_summary,
            "available_power": state.available_power,
            "target_power": state.target_power,
            "start_delay_remaining": state.start_delay_remaining,
            "grid_power": state.grid_power,
            "ev_power": state.ev_power,
            "solar_power": state.solar_power,
            "home_load_power": state.home_load_power,
            "battery_power": state.battery_power,
            "battery_charge_power": state.battery_charge_power,
            "battery_discharge_power": state.battery_discharge_power,
            "battery_power_used": state.battery_power_used,
            "battery_max_charge_power": state.battery_max_charge_power,
            "battery_soc": state.battery_soc,
            "battery_reserve_power": state.battery_reserve_power,
            "battery_reserve_shortfall_power": state.battery_reserve_shortfall_power,
            "surplus_source": state.surplus_source,
            "target_export_power": state.target_export_power,
            "deadband_power": state.deadband_power,
            "raw_target_current": state.raw_target_current,
            "target_current": state.target_current,
            "theoretical_target_current": state.theoretical_target_current,
            "reported_current_limit": state.reported_current_limit,
            "unused_export_power": state.unused_export_power,
            "excess_import_power": state.excess_import_power,
            "residual_export_remaining": state.residual_export_remaining,
            "deadband_active": state.deadband_active,
            "ramp_limited": state.ramp_limited,
            "ramp_direction": state.ramp_direction,
            "current_limit_reason": state.current_limit_reason,
            "decision_reason": state.decision_reason,
            "missing_data_reason": state.missing_data_reason,
        }


SOLAR_BALANCE_SENSORS: tuple[PrismSolarBalanceSensorEntityDescription, ...] = (
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_status_{}",
        device_class=SensorDeviceClass.ENUM,
        options=[
            SOLAR_BALANCE_DISABLED,
            SOLAR_BALANCE_WAITING_DATA,
            SOLAR_BALANCE_WAITING_BATTERY_DATA,
            SOLAR_BALANCE_WAITING_SOLAR_MODE,
            SOLAR_BALANCE_WAITING_STABLE_SURPLUS,
            SOLAR_BALANCE_PAUSED_LOW_SURPLUS,
            SOLAR_BALANCE_EXTERNAL_PAUSED,
            SOLAR_BALANCE_CHARGING_SURPLUS,
            SOLAR_BALANCE_LOW_SURPLUS_KEEP_CHARGING,
        ],
        has_entity_name=True,
        translation_key="solar_balance_status",
        value_key="status",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_surplus_current_{}",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        has_entity_name=True,
        translation_key="solar_balance_surplus_current",
        value_key="surplus_current",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_start_countdown_{}",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_start_countdown",
        value_key="start_delay_remaining",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_available_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_available_power",
        value_key="available_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_battery_power_used_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_battery_power_used",
        value_key="battery_power_used",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_grid_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_grid_power",
        value_key="grid_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_solar_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_solar_power",
        value_key="solar_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_home_load_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_home_load_power",
        value_key="home_load_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_target_current_{}",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        has_entity_name=True,
        translation_key="solar_balance_target_current",
        value_key="target_current",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_raw_target_current_{}",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        has_entity_name=True,
        translation_key="solar_balance_raw_target_current",
        value_key="raw_target_current",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_theoretical_target_current_{}",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        has_entity_name=True,
        translation_key="solar_balance_theoretical_target_current",
        value_key="theoretical_target_current",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_battery_reserve_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_battery_reserve_power",
        value_key="battery_reserve_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_battery_reserve_shortfall_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_battery_reserve_shortfall_power",
        value_key="battery_reserve_shortfall_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_target_export_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_target_export_power",
        value_key="target_export_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_unused_export_power_{}",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_unused_export_power",
        value_key="unused_export_power",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_residual_export_countdown_{}",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="solar_balance_residual_export_countdown",
        value_key="residual_export_remaining",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_decision_reason_{}",
        device_class=SensorDeviceClass.ENUM,
        options=[
            SOLAR_BALANCE_DISABLED,
            SOLAR_BALANCE_WAITING_DATA,
            SOLAR_BALANCE_WAITING_BATTERY_DATA,
            SOLAR_BALANCE_WAITING_SOLAR_MODE,
            SOLAR_BALANCE_WAITING_STABLE_SURPLUS,
            SOLAR_BALANCE_PAUSED_LOW_SURPLUS,
            SOLAR_BALANCE_EXTERNAL_PAUSED,
            SOLAR_BALANCE_CHARGING_SURPLUS,
            SOLAR_BALANCE_LOW_SURPLUS_KEEP_CHARGING,
        ],
        has_entity_name=True,
        translation_key="solar_balance_decision_reason",
        value_key="decision_reason",
    ),
    PrismSolarBalanceSensorEntityDescription(
        key="solar_balance_decision_summary_{}",
        has_entity_name=True,
        translation_key="solar_balance_decision_summary",
        value_key="decision_summary",
    ),
)

SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="current_state_{}",
        topic="{}/state",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "waiting", "charging", "pause"],
        has_entity_name=True,
        translation_key="current_state",
    ),
    PrismSensorEntityDescription(
        key="power_grid_voltage_{}",
        topic="{}/volt",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="power_grid_voltage",
    ),
    PrismSensorEntityDescription(
        key="output_power_{}",
        topic="{}/w",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_power",
    ),
    PrismSensorEntityDescription(
        key="output_current_{}",
        topic="{}/amp",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_current",
    ),
    PrismSensorEntityDescription(
        key="output_car_current_{}",
        topic="{}/pilot",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_car_current",
    ),
    PrismSensorEntityDescription(
        key="current_set_by_user_{}",
        topic="{}/user_amp",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="current_set_by_user",
    ),
    PrismSensorEntityDescription(
        key="session_time_{}",
        topic="{}/session_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="session_time",
    ),
    PrismSensorEntityDescription(
        key="session_output_energy_{}",
        topic="{}/wh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="session_output_energy",
    ),
    PrismSensorEntityDescription(
        key="total_output_energy_{}",
        topic="{}/wh_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="total_output_energy",
    ),
    PrismSensorEntityDescription(
        key="current_port_mode_{}",
        topic="{}/mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "solar",
            "normal",
            "paused",
            "hybrid",
            "suspended",
            "unknown",
            "autolimit",
        ],
        has_entity_name=True,
        translation_key="current_port_mode",
    ),
)

BASE_SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="input_grid_power",
        topic="energy_data/power_grid",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="input_grid_power",
    ),
    PrismSensorEntityDescription(
        key="core_temperature",
        topic="0/info/temperature/core",
        expire_after=86400,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="core_temperature",
    ),
)

POWERWALL_SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="powerwall_solar",
        topic="energy_data/power_solar",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="powerwall_solar",
    ),
    PrismSensorEntityDescription(
        key="powerwall_house",
        topic="energy_data/power_house",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="powerwall_house",
    ),
)

VSENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="input_grid_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        has_entity_name=True,
        translation_key="input_grid_energy",
    )
]
