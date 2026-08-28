"""Sensor platform for the BLUETTI integration."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
import logging
from typing import TypedDict, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BluettiConfigEntry
from .entity import BluettiEntity
from .models import BluettiData, BluettiDevice, BluettiState

__LOGGER__ = logging.getLogger(__name__)

# Entities only read from the coordinator and never poll or call the API
# themselves, so there is no need to limit concurrent updates.
PARALLEL_UPDATES = 0


class BaseSensorMetaInfo(TypedDict):
    """Static per-sensor-type metadata looked up from SENSOR_MAP."""

    device_class: SensorDeviceClass
    state_class: SensorStateClass | None
    unit: str | None


class NamedSensorMetaInfo(BaseSensorMetaInfo):
    """BaseSensorMetaInfo plus the display name for one specific sensor."""

    name: str


SENSOR_MAP: dict[str, BaseSensorMetaInfo] = {
    "SensorDeviceClass.BATTERY": {
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
    },
    "SensorDeviceClass.ENUM": {
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
    },
    "SensorDeviceClass.DURATION": {
        "device_class": SensorDeviceClass.DURATION,
        "state_class": None,
        "unit": "min",
    },
    "SensorDeviceClass.POWER": {
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "W",
    },
}


def _power_value_getter(state: BluettiState) -> Callable[[], str | float | None]:
    """Bind `state` by value, not by the loop variable's final reference."""
    return lambda: state.fn_value


def _estimated_power_value_getter(
    sensor: BluettiEstimatedBatteryPowerSensor,
) -> Callable[[], str | float | None]:
    """Bind `sensor` by value, not by the loop variable's final reference."""
    return lambda: sensor.native_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bluetti sensors from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices
    entities: list[BluettiEntity] = []

    for device in bluetti_devices.devices:
        for state in device.states:
            if state.fn_type == "SENSOR" and state.sensor_info:
                sensor_type = state.sensor_info.get("sensorType") or ""
                sensor_class = SENSOR_MAP.get(sensor_type)
                if sensor_class is None:
                    __LOGGER__.warning(
                        "Unknown sensor type '%s' for fn_code=%s, skipping",
                        sensor_type,
                        state.fn_code,
                    )
                    continue
                meta: NamedSensorMetaInfo = {
                    "name": state.fn_name,
                    # "unit" is missing entirely for some sensorInfo types
                    # (e.g. ENUM), not just empty.
                    "unit": state.sensor_info.get("unit") or sensor_class["unit"],
                    "device_class": sensor_class["device_class"],
                    "state_class": sensor_class["state_class"],
                }
                entities.append(BluettiSensor(device, state, meta))
                if meta["device_class"] == SensorDeviceClass.POWER:
                    # Bluetti reports power (W), never energy - integrate it
                    # over time like a Riemann-sum helper would.
                    entities.append(
                        BluettiEnergySensor(device, state, _power_value_getter(state))
                    )

        # Some models (e.g. Balco260) don't report battery charge/discharge
        # power directly - approximate it from the power balance of what
        # they do report (PV + grid input - AC load).
        pv_state = device.get_state("PVAllTotalPower")
        grid_state = device.get_state("GridAllTotalPower")
        ac_load_state = device.get_state("ACLoadAllTotalPower")
        if pv_state and grid_state and ac_load_state:
            for fn_code, name, charging in (
                (
                    "EstimatedBatteryChargePower",
                    "Battery Charge Power (Estimated)",
                    True,
                ),
                (
                    "EstimatedBatteryDischargePower",
                    "Battery Discharge Power (Estimated)",
                    False,
                ),
            ):
                battery_sensor = BluettiEstimatedBatteryPowerSensor(
                    device,
                    pv_state,
                    grid_state,
                    ac_load_state,
                    fn_code=fn_code,
                    name=name,
                    charging=charging,
                )
                entities.append(battery_sensor)
                entities.append(
                    BluettiEnergySensor(
                        device,
                        battery_sensor._state_obj,  # noqa: SLF001 - both classes live in this module
                        _estimated_power_value_getter(battery_sensor),
                    )
                )

    if entities:
        async_add_entities(entities)


class BluettiSensor(BluettiEntity, SensorEntity):
    """Bluetti sensor for numeric or enum states."""

    def __init__(
        self, device: BluettiDevice, state: BluettiState, meta: NamedSensorMetaInfo
    ) -> None:
        """Initialize the sensor from its owning device, state, and metadata."""
        super().__init__(device, state)
        self._meta = meta

        self._attr_name = meta["name"]
        self._attr_device_class = meta["device_class"]
        self._attr_state_class = meta["state_class"]
        self._attr_native_unit_of_measurement = meta["unit"]
        if meta["device_class"] == SensorDeviceClass.ENUM and state.support_mode_values:
            self._attr_options = [str(v["name"]) for v in state.support_mode_values]

    @property
    @override
    def native_value(self) -> str:
        """Return the state's current value, or its mode name if it's a mode."""
        if self._state_obj.support_mode_values:
            return self._state_obj.get_name_for_value()
        return self._state_obj.fn_value


class BluettiEnergySensor(BluettiEntity, RestoreSensor):
    """Cumulated energy (kWh) integrated from a BLUETTI power (W) sensor.

    Mirrors what a manually added Home Assistant "Integral - Riemann sum"
    helper (trapezoidal method, kilo prefix, hours) would compute on top of
    the power sensor, but built in so it works without any manual setup.

    The power value is read via `power_getter` rather than a fixed state
    object, so this can integrate either a real power sensor's raw value or
    a computed one (e.g. BluettiEstimatedBatteryPowerSensor's estimate).
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        device: BluettiDevice,
        identity_state: BluettiState,
        power_getter: Callable[[], str | float | None],
    ) -> None:
        """Initialize the energy sensor that will integrate power_getter's readings."""
        super().__init__(device, identity_state)
        self._power_getter = power_getter

        # identity_state's fn_code is shared with the sensor it integrates;
        # this companion entity needs its own identity.
        self._attr_unique_id = f"{device.device_id}_{identity_state.fn_code}_energy"
        self._attr_translation_key = None
        self._attr_name = f"{identity_state.fn_name} Energy"

        self._total_kwh: float = 0.0
        self._last_power_w: float | None = None
        self._last_updated: datetime | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last integrated total and starting power reading."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(
            last_data.native_value, (int, float, str, Decimal)
        ):
            self._total_kwh = float(last_data.native_value)

        self._last_power_w = self._current_power_w() if self.available else None
        self._last_updated = dt_util.utcnow()

    def _current_power_w(self) -> float | None:
        try:
            value = self._power_getter()
            return float(value) if value is not None else None
        except TypeError, ValueError:
            return None

    @override
    def _handle_coordinator_update(self) -> None:
        now = dt_util.utcnow()
        current_w = self._current_power_w() if self.available else None

        if (
            current_w is not None
            and self._last_power_w is not None
            and self._last_updated is not None
        ):
            elapsed_hours = (now - self._last_updated).total_seconds() / 3600
            average_w = (self._last_power_w + current_w) / 2
            self._total_kwh += (average_w * elapsed_hours) / 1000

        self._last_power_w = current_w
        self._last_updated = now

        super()._handle_coordinator_update()

    @property
    @override
    def native_value(self) -> float:
        """Return the total energy integrated so far, in kWh."""
        return round(self._total_kwh, 4)


class BluettiEstimatedBatteryPowerSensor(BluettiEntity, SensorEntity):
    """Estimated battery charge or discharge power.

    BLUETTI's cloud API does not report battery charge/discharge power
    directly on every model (e.g. Balco260) - only PV, grid, and AC load
    totals. This estimates it from the power balance
    (PV + grid input - AC load), assuming no separate DC load and no
    conversion losses. That makes it accurate at rest (net ~= 0) but only
    an approximation while actively charging or discharging - it is not a
    real measurement.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W"

    def __init__(
        self,
        device: BluettiDevice,
        pv_state: BluettiState,
        grid_state: BluettiState,
        ac_load_state: BluettiState,
        *,
        fn_code: str,
        name: str,
        charging: bool,
    ) -> None:
        """Initialize the estimator from the three real states it derives from."""
        identity_state = BluettiState(
            fn_code=fn_code, fn_name=name, fn_value="0", fn_type="SENSOR"
        )
        super().__init__(device, identity_state)
        self._pv_state = pv_state
        self._grid_state = grid_state
        self._ac_load_state = ac_load_state
        self._charging = charging

        self._attr_translation_key = None
        self._attr_name = name

    def _net_power_w(self) -> float | None:
        """Positive = surplus available to charge; negative = drawn from the battery.

        Deliberately omits DC load from the balance: no diagnostics dump in
        doc/diagnostics/ (nor the HACS custom_components/ version this was
        ported from) has ever reported a DC-load fn_code for a model that
        needs this estimate (Balco260 - a fixed AC-coupled unit with no DC
        output port to speak of). If a model that both needs this estimate
        and has real DC output ever shows up, this estimate would need that
        term too - left out rather than guessed at, per this project's own
        rule against inventing unverified fields.
        """
        try:
            return (
                float(self._pv_state.fn_value)
                + float(self._grid_state.fn_value)
                - float(self._ac_load_state.fn_value)
            )
        except TypeError, ValueError:
            return None

    @property
    @override
    def native_value(self) -> float | None:
        """Return the estimated charge or discharge power, whichever this sensor tracks."""
        net = self._net_power_w()
        if net is None:
            return None
        return max(net, 0.0) if self._charging else max(-net, 0.0)
