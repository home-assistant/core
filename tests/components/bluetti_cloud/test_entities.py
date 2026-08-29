"""Tests for the BLUETTI sensor platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.bluetti_cloud.const import DOMAIN
from homeassistant.components.bluetti_cloud.coordinator import BluettiDeviceCoordinator
from homeassistant.components.bluetti_cloud.models import BluettiDevice, BluettiState
from homeassistant.components.bluetti_cloud.sensor import (
    BluettiEnergySensor,
    BluettiEstimatedBatteryPowerSensor,
    BluettiSensor,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _make_coordinator(hass: HomeAssistant) -> BluettiDeviceCoordinator:
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test Device",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SOC",
                "fnName": "Battery Level",
                "fnValue": "80",
                "fnType": "SENSOR",
            },
            {
                "fnCode": "SetCtrlAc",
                "fnName": "AC Output",
                "fnValue": "0",
                "fnType": "SWITCH",
            },
            {
                "fnCode": "SetCtrlWorkMode",
                "fnName": "Work Mode",
                "fnValue": "0",
                "fnType": "SELECT",
                "supportModeValues": [
                    {"code": "0", "name": "Standard"},
                    {"code": "1", "name": "Silent"},
                ],
            },
            {
                "fnCode": "InvWorkState",
                "fnName": "Inverter Status",
                "fnValue": "0",
                "fnType": "SELECT",
                "supportModeValues": [{"code": "0", "name": "Idle"}],
            },
        ],
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return BluettiDeviceCoordinator(hass, entry, device)


async def test_sensor_uses_has_entity_name_and_device_info(hass: HomeAssistant) -> None:
    """Sensor uses has entity name and device info."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("SOC")
    meta = {
        "name": state.fn_name,
        "unit": "%",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": None,
    }

    entity = BluettiSensor(coordinator.device, state, meta)

    assert entity.has_entity_name is True
    # "soc" has a real strings.json translation (see _TRANSLATED_FN_CODES in
    # sensor.py), so _attr_name is deliberately left unset in favor of
    # BluettiEntity's translation_key - resolving that into a display name
    # needs a real platform/hass wiring this bare entity doesn't have; see
    # test_sensor_setup_entry_resolves_translated_names in test_setup_entry.py
    # for that end-to-end check.
    assert entity.translation_key == "soc"
    assert not hasattr(entity, "_attr_name")
    assert entity.unique_id == "SN1_SOC"
    assert entity.device_info["identifiers"] == {(DOMAIN, "SN1")}
    assert entity.device_info["serial_number"] == "SN1"
    assert entity.native_value == "80"
    assert entity.available is True


async def test_sensor_falls_back_to_fn_name_for_an_untranslated_fn_code(
    hass: HomeAssistant,
) -> None:
    """An fn_code with no strings.json entry still gets a usable name."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test Device",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SomeFutureField",
                "fnName": "Some Future Field",
                "fnValue": "1",
                "fnType": "SENSOR",
            }
        ],
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    state = coordinator.device.get_state("SomeFutureField")
    meta = {
        "name": state.fn_name,
        "unit": None,
        "device_class": None,
        "state_class": None,
    }

    entity = BluettiSensor(coordinator.device, state, meta)

    assert entity.translation_key == "somefuturefield"
    assert entity._attr_name == "Some Future Field"


async def test_sensor_unavailable_when_device_offline(hass: HomeAssistant) -> None:
    """Sensor unavailable when device offline."""
    coordinator = _make_coordinator(hass)
    coordinator.device.on_line = "0"
    state = coordinator.device.get_state("SOC")
    meta = {
        "name": state.fn_name,
        "unit": "%",
        "device_class": None,
        "state_class": None,
    }

    entity = BluettiSensor(coordinator.device, state, meta)

    assert entity.available is False


async def test_power_switch_state_stays_available_while_device_offline(
    hass: HomeAssistant,
) -> None:
    """The power switch itself must stay controllable when offline."""
    coordinator = _make_coordinator(hass)
    coordinator.device.on_line = "0"
    state = BluettiState(
        fn_code="SetCtrlPowerOn", fn_name="Power", fn_value="1", fn_type="SWITCH"
    )
    meta = {
        "name": state.fn_name,
        "unit": None,
        "device_class": None,
        "state_class": None,
    }

    entity = BluettiSensor(coordinator.device, state, meta)

    assert entity.available is True


async def test_sensor_unavailable_when_coordinator_update_failed(
    hass: HomeAssistant,
) -> None:
    """Sensor unavailable when coordinator update failed."""
    coordinator = _make_coordinator(hass)
    coordinator.last_update_success = False
    state = coordinator.device.get_state("SOC")
    meta = {
        "name": state.fn_name,
        "unit": "%",
        "device_class": None,
        "state_class": None,
    }

    entity = BluettiSensor(coordinator.device, state, meta)

    assert entity.available is False


def _add_power_state(coordinator) -> BluettiState:
    power_state = BluettiState(
        fn_code="PVAllTotalPower",
        fn_name="PV Input Power",
        fn_value="100",
        fn_type="SENSOR",
    )
    coordinator.device.states.append(power_state)
    return power_state


async def test_energy_sensor_has_distinct_unique_id_and_energy_attributes(
    hass: HomeAssistant,
) -> None:
    """Energy sensor has distinct unique id and energy attributes."""
    coordinator = _make_coordinator(hass)
    power_state = _add_power_state(coordinator)
    power_sensor = BluettiSensor(
        coordinator.device,
        power_state,
        {
            "name": power_state.fn_name,
            "unit": "W",
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
        },
    )

    energy_sensor = BluettiEnergySensor(
        coordinator.device, power_state, lambda: power_state.fn_value
    )

    # Both entities share the same underlying state (same fn_code), so the
    # energy companion must not collide with the power sensor's unique_id.
    assert energy_sensor.unique_id == "SN1_PVAllTotalPower_energy"
    assert energy_sensor.unique_id != power_sensor.unique_id
    assert energy_sensor.name == "PV Input Power Energy"
    assert energy_sensor.device_class == SensorDeviceClass.ENERGY
    assert energy_sensor.native_unit_of_measurement == "kWh"
    assert energy_sensor.native_value == 0.0


async def test_energy_sensor_integrates_power_trapezoidally_over_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Energy sensor integrates power trapezoidally over time."""
    coordinator = _make_coordinator(hass)
    power_state = _add_power_state(coordinator)
    entity = BluettiEnergySensor(
        coordinator.device, power_state, lambda: power_state.fn_value
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_pv_energy"

    await entity.async_added_to_hass()

    freezer.tick(timedelta(hours=1))
    power_state.fn_value = "300"
    entity._handle_coordinator_update()

    # Trapezoidal rule: (100 W + 300 W) / 2 = 200 W average over 1 hour =
    # 0.2 kWh - the same result a manually added "Integral - Riemann sum"
    # helper (trapezoidal, kilo prefix, hours) would compute.
    assert entity.native_value == 0.2

    freezer.tick(timedelta(hours=2))
    power_state.fn_value = "300"
    entity._handle_coordinator_update()

    # Constant 300 W for 2 more hours = 0.6 kWh, cumulated on top of the 0.2
    # already integrated.
    assert entity.native_value == 0.8

    await coordinator.async_shutdown()


async def test_energy_sensor_restores_previous_total_on_startup(
    hass: HomeAssistant,
) -> None:
    """Energy sensor restores previous total on startup."""
    coordinator = _make_coordinator(hass)
    power_state = _add_power_state(coordinator)
    entity = BluettiEnergySensor(
        coordinator.device, power_state, lambda: power_state.fn_value
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_pv_energy"

    async def fake_last_sensor_data():
        return SensorExtraStoredData(42.5, "kWh")

    entity.async_get_last_sensor_data = fake_last_sensor_data

    await entity.async_added_to_hass()

    assert entity.native_value == 42.5

    await coordinator.async_shutdown()


async def test_energy_sensor_treats_non_numeric_power_value_as_unknown(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Energy sensor treats non numeric power value as unknown."""
    coordinator = _make_coordinator(hass)
    power_state = _add_power_state(coordinator)
    entity = BluettiEnergySensor(
        coordinator.device, power_state, lambda: power_state.fn_value
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_pv_energy"

    await entity.async_added_to_hass()

    freezer.tick(timedelta(hours=1))
    power_state.fn_value = None  # e.g. a transient malformed API response
    entity._handle_coordinator_update()
    # A non-numeric reading can't contribute to the trapezoidal area, and
    # must not crash the update either.
    assert entity.native_value == 0.0

    freezer.tick(timedelta(hours=1))
    power_state.fn_value = "not-a-number"  # e.g. a malformed getter result
    entity._handle_coordinator_update()
    assert entity.native_value == 0.0

    await coordinator.async_shutdown()


async def test_energy_sensor_skips_integration_across_unavailable_gap(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Energy sensor skips integration across unavailable gap."""
    coordinator = _make_coordinator(hass)
    power_state = _add_power_state(coordinator)
    entity = BluettiEnergySensor(
        coordinator.device, power_state, lambda: power_state.fn_value
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_pv_energy"

    await entity.async_added_to_hass()

    coordinator.device.on_line = "0"
    freezer.tick(timedelta(hours=5))
    entity._handle_coordinator_update()
    # No area is computed while the device (and thus this sensor) is
    # unavailable, to avoid a bogus energy spike once it reconnects.
    assert entity.native_value == 0.0

    coordinator.device.on_line = "1"
    freezer.tick(timedelta(hours=1))
    power_state.fn_value = "200"
    entity._handle_coordinator_update()
    # Only one real sample is known since coming back online, so no area
    # can be computed yet for this first post-outage update.
    assert entity.native_value == 0.0

    freezer.tick(timedelta(hours=1))
    power_state.fn_value = "200"
    entity._handle_coordinator_update()
    assert entity.native_value == 0.2

    await coordinator.async_shutdown()


def _add_balance_states(coordinator, pv="0", grid="0", ac_load="0"):
    device = coordinator.device
    pv_state = BluettiState(
        fn_code="PVAllTotalPower",
        fn_name="PV Input Power",
        fn_value=pv,
        fn_type="SENSOR",
    )
    grid_state = BluettiState(
        fn_code="GridAllTotalPower",
        fn_name="Grid Input Power",
        fn_value=grid,
        fn_type="SENSOR",
    )
    ac_load_state = BluettiState(
        fn_code="ACLoadAllTotalPower",
        fn_name="AC Load Power",
        fn_value=ac_load,
        fn_type="SENSOR",
    )
    device.states.extend([pv_state, grid_state, ac_load_state])
    return pv_state, grid_state, ac_load_state


def _make_estimated_battery_sensors(device, pv_state, grid_state, ac_load_state):
    charge_sensor = BluettiEstimatedBatteryPowerSensor(
        device,
        pv_state,
        grid_state,
        ac_load_state,
        fn_code="EstimatedBatteryChargePower",
        name="Battery Charge Power (Estimated)",
        charging=True,
    )
    discharge_sensor = BluettiEstimatedBatteryPowerSensor(
        device,
        pv_state,
        grid_state,
        ac_load_state,
        fn_code="EstimatedBatteryDischargePower",
        name="Battery Discharge Power (Estimated)",
        charging=False,
    )
    return charge_sensor, discharge_sensor


async def test_estimated_battery_power_sensor_reports_charging_when_surplus(
    hass: HomeAssistant,
) -> None:
    """Estimated battery power sensor reports charging when surplus."""
    # BLUETTI's cloud API doesn't report battery charge/discharge power for
    # every model (e.g. Balco260) - only PV/grid/AC load totals - so this is
    # estimated from the power balance instead.
    coordinator = _make_coordinator(hass)
    pv_state, grid_state, ac_load_state = _add_balance_states(
        coordinator, pv="500", grid="0", ac_load="200"
    )
    charge_sensor, discharge_sensor = _make_estimated_battery_sensors(
        coordinator.device, pv_state, grid_state, ac_load_state
    )

    # 500 W PV - 200 W AC load = 300 W surplus -> charging, not discharging.
    assert charge_sensor.native_value == 300.0
    assert discharge_sensor.native_value == 0.0
    assert charge_sensor.unique_id == "SN1_EstimatedBatteryChargePower"
    assert charge_sensor.device_class == SensorDeviceClass.POWER
    assert charge_sensor.native_unit_of_measurement == "W"


async def test_estimated_battery_power_sensor_reports_discharging_when_deficit(
    hass: HomeAssistant,
) -> None:
    """Estimated battery power sensor reports discharging when deficit."""
    coordinator = _make_coordinator(hass)
    pv_state, grid_state, ac_load_state = _add_balance_states(
        coordinator, pv="0", grid="0", ac_load="400"
    )
    charge_sensor, discharge_sensor = _make_estimated_battery_sensors(
        coordinator.device, pv_state, grid_state, ac_load_state
    )

    # No PV, no grid, 400 W AC load -> the deficit can only come from the battery.
    assert discharge_sensor.native_value == 400.0
    assert charge_sensor.native_value == 0.0


async def test_estimated_battery_power_sensor_zero_at_rest(hass: HomeAssistant) -> None:
    """Estimated battery power sensor zero at rest."""
    coordinator = _make_coordinator(hass)
    # Matches the real Balco260 diagnostic dump this was modeled on:
    # PV=0, Grid=395, ACLoad=395, SOC=100% - grid fully covers the load.
    pv_state, grid_state, ac_load_state = _add_balance_states(
        coordinator, pv="0", grid="395", ac_load="395"
    )
    charge_sensor, discharge_sensor = _make_estimated_battery_sensors(
        coordinator.device, pv_state, grid_state, ac_load_state
    )

    assert charge_sensor.native_value == 0.0
    assert discharge_sensor.native_value == 0.0


async def test_estimated_battery_power_sensor_handles_non_numeric_input(
    hass: HomeAssistant,
) -> None:
    """Estimated battery power sensor handles non numeric input."""
    coordinator = _make_coordinator(hass)
    pv_state, grid_state, ac_load_state = _add_balance_states(coordinator)
    grid_state.fn_value = None  # e.g. a transient malformed API response
    charge_sensor, _ = _make_estimated_battery_sensors(
        coordinator.device, pv_state, grid_state, ac_load_state
    )

    assert charge_sensor.native_value is None
