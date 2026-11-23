"""Tests for Daikin Onecta sensor entities."""

from collections.abc import Callable
from dataclasses import replace
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from daikin_onecta.models import Characteristic, GatewayDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.components.daikin_onecta.entity import EntityIdChecker
from homeassistant.components.daikin_onecta.sensor import (
    SENSOR_DESCRIPTIONS,
    DaikinEnergySensor,
    DaikinValueSensor,
    EnergySensorDetails,
    ValueSensorDetails,
    _create_device_sensors,
    _native_unit,
    add_energy_sensors,
)
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import (
    _async_fire_coordinator_update,
    _async_setup_fixture,
    _load_gateway_devices,
)


def _set_cooling_calculated_temperature(gateway: GatewayDevice) -> None:
    """Set different calculated temperatures for the current and first modes."""
    point = gateway.management_points_by_type("climateControl")[0]
    point.operation_mode = Characteristic(
        value="cooling", values=["auto", "cooling", "heating"]
    )
    assert point.temperature_control is not None
    operation_modes = point.temperature_control.value.operation_modes
    operation_modes["auto"].setpoints["calculatedLeavingWaterTemperature"].value = 45
    operation_modes["cooling"].setpoints["calculatedLeavingWaterTemperature"].value = 38


def _remove_cooling_calculated_temperature(gateway: GatewayDevice) -> None:
    """Make the first mode the fallback when the current mode lacks a value."""
    point = gateway.management_points_by_type("climateControl")[0]
    point.operation_mode = Characteristic(
        value="cooling", values=["auto", "cooling", "heating"]
    )
    assert point.temperature_control is not None
    operation_modes = point.temperature_control.value.operation_modes
    operation_modes["auto"].setpoints["calculatedLeavingWaterTemperature"].value = 45
    operation_modes["cooling"].setpoints.pop("calculatedLeavingWaterTemperature")


async def test_calculated_leaving_water_temperature_is_a_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose Daikin's non-settable calculated temperature as a sensor."""
    await _async_setup_fixture(hass, config_entry, "gas")
    gateway = _load_gateway_devices("gas")[0]

    calculated_setpoint_sensor = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{gateway.id}_1_setpoint_calculatedLeavingWaterTemperature",
    )
    leaving_water_setpoint_sensor = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{gateway.id}_1_setpoint_leavingWaterTemperature",
    )
    calculated_climate_entity = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{gateway.id}_1_calculatedLeavingWaterTemperature",
    )
    leaving_water_climate_entity = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{gateway.id}_1_leavingWaterTemperature",
    )

    assert calculated_setpoint_sensor is not None
    assert leaving_water_setpoint_sensor is None
    calculated_state = hass.states.get(calculated_setpoint_sensor)
    assert calculated_state is not None and calculated_state.state == "50"
    assert calculated_climate_entity is None
    assert leaving_water_climate_entity is not None


@pytest.mark.parametrize(
    ("prepare_gateway", "expected_value"),
    [
        pytest.param(
            _set_cooling_calculated_temperature,
            "38",
            id="current-operation-mode",
        ),
        pytest.param(
            _remove_cooling_calculated_temperature,
            "45",
            id="fallback-to-first-mode",
        ),
    ],
)
async def test_calculated_lwt_sensor_uses_current_mode_then_falls_back(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    prepare_gateway: Callable[[GatewayDevice], None],
    expected_value: str,
) -> None:
    """Prefer the current operation's calculated LWT and fall back if absent."""
    await _async_setup_fixture(hass, config_entry, "gas")
    coordinator = config_entry.runtime_data
    gateway = next(iter(coordinator.data.values())).device
    prepare_gateway(gateway)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    sensor_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{gateway.id}_1_setpoint_calculatedLeavingWaterTemperature",
    )
    assert sensor_id is not None
    state = hass.states.get(sensor_id)
    assert state is not None
    assert state.state == expected_value


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


@pytest.mark.parametrize("key", ["leavingWaterOffset", "deltaD"])
def test_temperature_differences_use_delta_device_class(key: str) -> None:
    """Treat Daikin offsets and differences as temperature deltas."""
    assert SENSOR_DESCRIPTIONS[key].device_class is SensorDeviceClass.TEMPERATURE_DELTA


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
    entity_id = "sensor.altherma_setpoint_mode"
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


async def test_operation_mode_is_exposed_as_raw_enum_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose the native operation mode separately from the climate mode."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = next(
        point
        for point in device.device.management_points
        if point.embedded_id == "climateControlMainZone"
    )
    characteristic = point.scalar_characteristic("operationMode")
    assert characteristic is not None
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{device.id}_{point.embedded_id}_operationMode",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "cooling"
    assert "heating" in state.attributes["options"]

    characteristic.value = "heating"
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "heating"


async def test_boolean_value_is_not_exposed_as_numeric_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Boolean characteristics are not rendered as numeric sensor values."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = next(
        point
        for point in device.device.management_points
        if point.scalar_characteristic("controlMode") is not None
    )
    characteristic = point.scalar_characteristic("controlMode")
    assert characteristic is not None
    characteristic.value = True
    unique_id = f"{device.id}_{point.embedded_id}_controlMode"
    entity_id = entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None and state.state == "unknown"


async def test_empty_error_code_is_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Represent an empty Daikin error code as an unknown sensor state."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = next(
        point
        for point in device.device.management_points
        if point.scalar_characteristic("errorCode") is not None
    )
    characteristic = point.scalar_characteristic("errorCode")
    assert characteristic is not None
    characteristic.value = ""
    unique_id = f"{device.id}_{point.embedded_id}_errorCode"
    entity_id = entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None

    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None and state.state == "unknown"


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
        lambda *_: False,
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
        lambda *_: False,
    )

    assert sensors == []


@pytest.mark.parametrize(
    ("reported_unit", "expected_unit"),
    [("°F", "°F"), (None, UnitOfTemperature.CELSIUS)],
)
async def test_value_sensor_uses_daikin_unit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reported_unit: str | None,
    expected_unit: str,
) -> None:
    """Prefer Daikin's characteristic unit and retain the description fallback."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    characteristic = point.sensory_characteristic("tankTemperature")
    assert characteristic is not None
    characteristic.unit = reported_unit

    await _async_setup_fixture(
        hass, config_entry, "altherma_boost", gateway_devices=gateway_devices
    )
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    entity = DaikinValueSensor(
        device,
        coordinator,
        SENSOR_DESCRIPTIONS["tankTemperature"],
        ValueSensorDetails(point.embedded_id, "sensoryData", "tankTemperature"),
    )

    assert entity.native_unit_of_measurement == expected_unit


@pytest.mark.parametrize(
    ("reported_unit", "expected_unit"),
    [("MJ", "MJ"), (None, "kWh")],
)
async def test_energy_sensor_uses_daikin_unit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reported_unit: str | None,
    expected_unit: str,
) -> None:
    """Prefer Daikin's energy-source unit and retain the description fallback."""
    gateway_devices = _load_gateway_devices("altherma")
    device = gateway_devices[0]
    point = next(point for point in device.management_points if point.energy_aggregates)
    aggregate = point.energy_aggregates[0]
    assert aggregate.data_type == "consumption"
    energy_data = point.consumption
    assert energy_data is not None
    source = energy_data.source(aggregate.source)
    assert source is not None
    source.unit = reported_unit
    await _async_setup_fixture(
        hass, config_entry, "altherma", gateway_devices=gateway_devices
    )
    coordinator = config_entry.runtime_data
    current_device = coordinator.data[device.id]
    description_key = (
        f"{aggregate.operation_mode.capitalize()}Daily"
        f"{aggregate.source.capitalize()}{aggregate.data_type.capitalize()}"
    )
    entity = DaikinEnergySensor(
        current_device,
        coordinator,
        SENSOR_DESCRIPTIONS[description_key],
        EnergySensorDetails(
            point.embedded_id,
            aggregate.source,
            aggregate.operation_mode,
            aggregate.period,
            aggregate.data_type,
        ),
    )

    assert entity.native_unit_of_measurement == expected_unit


@pytest.mark.parametrize(
    ("unit", "description", "expected"),
    [
        ("not-a-unit", SENSOR_DESCRIPTIONS["roomTemperature"], "°C"),
        (
            "not-a-unit",
            SENSOR_DESCRIPTIONS["HeatingDailyElectricalConsumption"],
            "kWh",
        ),
    ],
)
def test_sensor_falls_back_for_unknown_native_unit(
    unit: str, description: SensorEntityDescription, expected: str
) -> None:
    """Use the entity-description unit when Daikin reports an unknown unit."""
    assert _native_unit(unit, description) == expected


async def test_sensors_become_unavailable_when_management_point_disappears(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Publish scalar and energy sensors unavailable through HA after removal."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("climateControl")[0]
    scalar_entity_id = "sensor.altherma_room_temperature"
    energy_entity_id = "sensor.altherma_heating_daily_electrical_consumption"
    assert hass.states.get(scalar_entity_id) is not None
    assert hass.states.get(energy_entity_id) is not None

    gateway.device.management_points.remove(point)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(scalar_entity_id).state == "unavailable"
    assert hass.states.get(energy_entity_id).state == "unavailable"


async def test_value_sensor_availability_uses_current_model_data(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reflect an in-memory characteristic removal before the next cloud poll."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("climateControl")[0]
    entity = hass.data[SENSOR_DOMAIN].get_entity("sensor.altherma_control_mode")
    assert isinstance(entity, DaikinValueSensor)

    assert entity.available
    point.characteristics.pop("controlMode")
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    assert not entity.available


async def test_disabled_value_sensor_is_not_rebuilt_on_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep disabled-by-default entity IDs reserved after Home Assistant aborts add."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    entity_entry = entity_registry.async_get("sensor.altherma_ip_address")
    assert entity_entry is not None and entity_entry.disabled_by is not None

    created_unique_ids: list[str] = []

    def track_created_entities(
        coordinator: OnectaDataUpdateCoordinator, is_known: EntityIdChecker
    ) -> list[DaikinValueSensor]:
        entities = _create_device_sensors(coordinator, is_known)
        created_unique_ids.extend(
            entity.unique_id for entity in entities if entity.unique_id is not None
        )
        return entities

    with patch(
        "homeassistant.components.daikin_onecta.sensor._create_device_sensors",
        side_effect=track_created_entities,
    ):
        await _async_fire_coordinator_update(hass, config_entry.runtime_data, freezer)

    assert entity_entry.unique_id not in created_unique_ids


async def test_limit_sensor_updates_through_coordinator_listener(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Publish account rate-limit changes through the HA entity state API."""
    registered = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{config_entry.unique_id}_rate_limit_remaining_day",
        config_entry=config_entry,
        disabled_by=None,
    )
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    coordinator.client.rate_limit = replace(
        coordinator.client.rate_limit, day_remaining=123
    )
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(registered.entity_id)
    assert state is not None
    assert state.state == "123"
