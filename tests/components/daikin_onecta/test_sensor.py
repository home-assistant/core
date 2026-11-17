"""Tests for Daikin Onecta sensor entities."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN, SENSOR_PERIOD_DAILY
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.components.daikin_onecta.entity_descriptions import (
    SENSOR_DESCRIPTIONS,
)
from homeassistant.components.daikin_onecta.sensor import (
    DaikinEnergySensor,
    DaikinLimitSensor,
    DaikinValueSensor,
    EnergySensorDetails,
    ValueSensorDetails,
    _native_unit,
    add_energy_sensors,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


@pytest.mark.parametrize(
    ("key", "options"),
    [
        (
            "controlMode",
            [
                "leaving_water_temperature",
                "external_room_temperature",
                "room_temperature",
            ],
        ),
        (
            "heatupMode",
            ["reheat_only", "reheat_schedule", "schedule_only", "scheduled_reheat"],
        ),
        (
            "setpointMode",
            [
                "fixed",
                "weather_dependent",
                "weather_dependent_heating_fixed_cooling",
                "weather_dependent_cooling_fixed_heating",
            ],
        ),
        (
            "airPurificationMode",
            [
                "manual_fan",
                "auto_fan",
                "econo",
                "anti_pollen",
                "circulator",
                "auto",
                "moist",
                "off",
            ],
        ),
        (
            "operationMode",
            [
                "fan_only",
                "heating",
                "cooling",
                "auto",
                "dry",
                "off",
                "heating_day",
                "heating_night",
                "humidification",
            ],
        ),
    ],
)
def test_string_mode_sensors_use_enum_options(key: str, options: list[str]) -> None:
    """Describe Daikin mode values as translated enums, not opaque strings."""
    description = SENSOR_DESCRIPTIONS[key]

    assert description.device_class is SensorDeviceClass.ENUM
    assert description.options == options


async def test_unknown_enum_value_keeps_sensor_updating(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Show unknown enum values as unknown without breaking future updates."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    point = next(
        point
        for point in device.device.management_points
        if point.scalar_characteristic("setpointMode") is not None
    )
    characteristic = point.scalar_characteristic("setpointMode")
    assert characteristic is not None
    entity_id = "sensor.altherma_climatecontrol_setpoint_mode"
    caplog.set_level(
        logging.DEBUG, logger="homeassistant.components.daikin_onecta.sensor"
    )

    characteristic.value = "weatherDependentHeatingFixedCooling"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "weather_dependent_heating_fixed_cooling"

    characteristic.value = "newDaikinOperationMode"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert caplog.text.count("Ignoring unsupported Daikin enum value") == 1


@pytest.mark.parametrize(
    "key",
    [
        "sgtin",
        "wifiConnectionSSID",
        "wifiConnectionStrength",
        "ssid",
        "ipAddress",
        "dateTime",
        "regionCode",
        "timeZone",
        "RatelimitRemainingDay",
    ],
)
def test_diagnostic_sensor_descriptions_are_disabled_by_default(key: str) -> None:
    """Keep identifiers and diagnostic-only values out of normal entity lists."""
    description = SENSOR_DESCRIPTIONS[key]
    assert description.entity_category is EntityCategory.DIAGNOSTIC
    assert description.entity_registry_enabled_default is False


async def test_diagnostic_entities_are_registered_but_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Create diagnostic registry entries without enabling their states."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    keys = {
        "sgtin",
        "wifiConnectionSSID",
        "wifiConnectionStrength",
        "ssid",
        "ipAddress",
        "dateTime",
        "regionCode",
        "timeZone",
        "RatelimitRemainingDay",
    }
    translations = {SENSOR_DESCRIPTIONS[key].translation_key for key in keys}
    entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == SENSOR_DOMAIN and entry.translation_key in translations
    ]
    assert len(entries) > 1
    assert f"{config_entry.unique_id}_rate_limit_remaining_day" in {
        entry.unique_id for entry in entries
    }
    for entry in entries:
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entry.entity_id) is None


@pytest.mark.parametrize("disabled_by", [None, er.RegistryEntryDisabler.USER])
async def test_existing_diagnostic_entity_preferences_are_preserved(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Do not replace users' existing enable/disable choices with defaults."""
    registered = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{config_entry.unique_id}_rate_limit_remaining_day",
        config_entry=config_entry,
        disabled_by=disabled_by,
    )

    await _async_setup_fixture(hass, config_entry, "mc80z")

    assert entity_registry.async_get(registered.entity_id).disabled_by is disabled_by
    assert (hass.states.get(registered.entity_id) is None) == (disabled_by is not None)


def test_unsupported_energy_aggregate_is_skipped() -> None:
    """Do not prevent platform setup for an unrepresented energy aggregate."""
    sensors = []

    add_energy_sensors(
        MagicMock(),
        MagicMock(),
        SimpleNamespace(
            embedded_id="outdoorUnit",
            management_point_type="outdoorUnit",
            energy_aggregates=[
                SimpleNamespace(
                    source="thermal",
                    operation_mode="heating",
                    period="day",
                    data_type="output",
                )
            ],
        ),
        sensors,
    )

    assert sensors == []


def test_unsupported_energy_period_is_skipped() -> None:
    """Do not prevent platform setup for an unknown Daikin energy period."""
    sensors = []

    add_energy_sensors(
        MagicMock(),
        MagicMock(),
        SimpleNamespace(
            embedded_id="outdoorUnit",
            management_point_type="outdoorUnit",
            energy_aggregates=[
                SimpleNamespace(
                    source="electrical",
                    operation_mode="heating",
                    period="quarter",
                    data_type="consumed",
                )
            ],
        ),
        sensors,
    )

    assert sensors == []


@pytest.mark.parametrize(
    ("reported_unit", "expected_unit"),
    [("°F", "°F"), (None, UnitOfTemperature.CELSIUS)],
)
def test_value_sensor_uses_daikin_unit(
    reported_unit: str | None, expected_unit: str
) -> None:
    """Prefer Daikin's characteristic unit and retain the description fallback."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    characteristic = point.sensory_characteristic("tankTemperature")
    assert characteristic is not None
    characteristic.unit = reported_unit

    entity = DaikinValueSensor(
        device,
        MagicMock(),
        SENSOR_DESCRIPTIONS["tankTemperature"],
        ValueSensorDetails(point.embedded_id, "sensoryData", "tankTemperature"),
    )

    assert entity.native_unit_of_measurement == expected_unit


@pytest.mark.parametrize(
    ("reported_unit", "expected_unit"),
    [("MJ", "MJ"), (None, "kWh")],
)
def test_energy_sensor_uses_daikin_unit(
    reported_unit: str | None, expected_unit: str
) -> None:
    """Prefer Daikin's energy-source unit and retain the description fallback."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma")[0])
    point = next(
        point for point in device.device.management_points if point.energy_aggregates
    )
    aggregate = point.energy_aggregates[0]
    energy_data = (
        point.consumption
        if aggregate.data_type == "consumption"
        else point.energy_output
    )
    source = energy_data.source(aggregate.source)
    assert source is not None
    source.unit = reported_unit
    description_key = (
        f"{aggregate.operation_mode.capitalize()}Daily"
        f"{aggregate.source.capitalize()}{aggregate.data_type.capitalize()}"
    )
    entity = DaikinEnergySensor(
        device,
        MagicMock(),
        SENSOR_DESCRIPTIONS[description_key],
        EnergySensorDetails(
            point.embedded_id,
            aggregate.source,
            aggregate.operation_mode,
            SENSOR_PERIOD_DAILY,
            aggregate.data_type,
        ),
    )

    assert entity.native_unit_of_measurement == expected_unit


@pytest.mark.parametrize(
    ("unit", "description", "expected"),
    [
        ("not-a-unit", SENSOR_DESCRIPTIONS["roomTemperature"], "not-a-unit"),
        (
            "not-a-unit",
            SENSOR_DESCRIPTIONS["HeatingDailyElectricalConsumption"],
            "not-a-unit",
        ),
    ],
)
def test_sensor_preserves_unknown_native_unit(
    unit: str, description, expected: str
) -> None:
    """Pass through Daikin unit strings that HA does not recognize."""
    assert _native_unit(unit, description) == expected


def test_energy_sensor_value_when_management_point_is_missing() -> None:
    """Return no energy value after its source point disappears."""
    entity = object.__new__(DaikinEnergySensor)
    entity._device = SimpleNamespace(management_point=lambda _: None)
    entity._embedded_id = "point"
    entity._period = SENSOR_PERIOD_DAILY
    entity._datatype = "consumption"
    entity._sensor_type = "electrical"
    entity._operation_mode = "heating"

    assert entity.sensor_value() is None


def test_value_sensor_value_when_management_point_is_missing() -> None:
    """Return no scalar value after its source point disappears."""
    entity = object.__new__(DaikinValueSensor)
    entity._device = SimpleNamespace(management_point=lambda _: None)
    entity._embedded_id = "point"
    entity._sub_type = None
    entity._value = "roomTemperature"

    assert entity.sensor_value() is None


def test_value_sensor_unavailable_when_point_disappears_between_checks() -> None:
    """Handle a point disappearing while availability is being evaluated."""
    entity = object.__new__(DaikinValueSensor)
    entity.coordinator = SimpleNamespace(last_update_success=True)
    entity._embedded_id = "point"
    entity._sub_type = None
    entity._value = "roomTemperature"
    entity._device = SimpleNamespace(
        available=True,
        management_point=MagicMock(side_effect=[SimpleNamespace(), None]),
    )

    assert not entity.available


def test_limit_sensor_updates_on_coordinator_refresh() -> None:
    """Refresh and publish the account-level rate-limit sensor value."""
    entity = object.__new__(DaikinLimitSensor)
    entity.coordinator = SimpleNamespace(rate_limits={"remaining_day": 123})
    entity._limit_key = "remaining_day"
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.native_value == 123
    entity.async_write_ha_state.assert_called_once_with()
