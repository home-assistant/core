"""Tests for runtime discovery of new gateways and supported capabilities."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import (
    Characteristic,
    GatewayDevice,
    ManagementPoint,
    Setpoint,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.daikin_onecta import (
    OnectaDataUpdateCoordinator,
    async_remove_config_entry_device,
)
from homeassistant.components.daikin_onecta.const import (
    BINARY_SENSOR_KEYS,
    DOMAIN,
    SENSOR_KEYS,
    SWITCH_KEYS,
    UPDATE_KEYS,
)
from homeassistant.components.daikin_onecta.discovery import (
    energy_description_key,
    has_air_purifier_power_control,
    has_climate_entity,
    scalar_platform,
    scalar_platform_for_point,
)
from homeassistant.components.daikin_onecta.switch import SWITCH_DESCRIPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockOnectaClient
from .platform_helpers import _async_setup_fixture, _load_gateway_devices


def test_sensor_keys_exclude_other_platform_keys() -> None:
    """Never create value sensors for binary, switch, update, or select keys."""
    assert SENSOR_KEYS.isdisjoint(BINARY_SENSOR_KEYS | SWITCH_KEYS | UPDATE_KEYS)
    assert "onOffMode" in SWITCH_KEYS
    assert "onOffMode" not in BINARY_SENSOR_KEYS
    assert "schedule" not in SENSOR_KEYS


def test_air_purification_mode_sensor_when_climate_entity_exists() -> None:
    """Keep purifier mode visible when a climate entity prevents a fan entity."""
    point = _load_gateway_devices("mc80z")[0].management_points_by_type(
        "climateControl"
    )[0]
    assert has_air_purifier_power_control(point)
    characteristic = point.scalar_characteristic("airPurificationMode")
    assert characteristic is not None

    with patch(
        "homeassistant.components.daikin_onecta.discovery.has_climate_entity",
        return_value=True,
    ):
        assert (
            scalar_platform_for_point(point, "airPurificationMode") is Platform.SENSOR
        )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("econoMode", Platform.SWITCH, id="econo-mode"),
        pytest.param("onOffMode", Platform.SWITCH, id="power"),
        pytest.param("streamerMode", Platform.SWITCH, id="streamer-mode"),
        pytest.param("ledEnabled", Platform.BINARY_SENSOR, id="led-enabled"),
        pytest.param("operationMode", Platform.SENSOR, id="operation-mode"),
        pytest.param("futureCharacteristic", None, id="unknown-characteristic"),
    ],
)
def test_scalar_platform(
    name: str,
    expected: Platform | None,
) -> None:
    """Classify supported scalar characteristics from their stable keys."""
    assert scalar_platform(name) is expected


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("onOffMode", id="climate-power"),
        pytest.param("powerfulMode", id="climate-boost"),
    ],
)
def test_offline_climate_controls_are_owned_by_climate(name: str) -> None:
    """Keep offline climate-owned controls off scalar platforms."""
    point = _load_gateway_devices("offlinedevice")[0].management_points_by_type(
        "climateControl"
    )[0]
    assert scalar_platform_for_point(point, name, gateway_online=False) is None


@pytest.mark.parametrize(
    ("name", "settable", "gateway_online", "expected_platform"),
    [
        pytest.param(
            "onOffMode",
            False,
            True,
            Platform.SWITCH,
            id="read-only-power-online",
        ),
        pytest.param(
            "onOffMode", False, False, Platform.SWITCH, id="read-only-power-offline"
        ),
        pytest.param(
            "powerfulMode", False, False, Platform.SWITCH, id="read-only-boost-offline"
        ),
        pytest.param("onOffMode", True, True, Platform.SWITCH, id="writable-power"),
        pytest.param("powerfulMode", False, True, Platform.SWITCH, id="boost"),
        pytest.param(
            "powerfulMode", True, False, Platform.SWITCH, id="writable-boost-offline"
        ),
    ],
)
def test_climate_control_without_supported_setpoint_is_exposed(
    name: str,
    settable: bool,
    gateway_online: bool,
    expected_platform: Platform | None,
) -> None:
    """Expose controls when no climate entity can own them."""
    point = ManagementPoint(
        embedded_id="read_only_climate_control",
        management_point_type="climateControl",
        characteristics={
            name: Characteristic(value="on", settable=settable, values=["on", "off"]),
        },
    )
    assert (
        scalar_platform_for_point(point, name, gateway_online=gateway_online)
        is expected_platform
    )


def test_read_only_climate_setpoint_keeps_climate_ownership() -> None:
    """Keep climate controls on the climate platform when setpoints are read-only."""
    point = deepcopy(
        _load_gateway_devices("dry")[0].management_points_by_type("climateControl")[0]
    )
    climate_control = point.climate_control
    assert climate_control is not None
    assert point.temperature_control is not None
    for operation in point.temperature_control.value.operation_modes.values():
        for setpoint in operation.setpoints.values():
            setpoint.settable = False

    assert has_climate_entity(point)
    assert scalar_platform_for_point(point, "onOffMode") is None


async def test_switch_platform_is_stable_when_writability_changes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep a power characteristic on the switch platform as writability flips."""
    devices = _load_gateway_devices("minimal_data")
    gateway = devices[0]
    point = ManagementPoint(
        embedded_id="independent_power",
        management_point_type="other",
        characteristics={
            "onOffMode": Characteristic(
                value="off", settable=False, values=["on", "off"]
            )
        },
    )
    gateway.management_points.append(point)

    await _async_setup_fixture(
        hass, config_entry, "minimal_data", gateway_devices=devices
    )
    coordinator = config_entry.runtime_data
    unique_id = f"{gateway.id}_{point.embedded_id}_onOffMode"
    switch_entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH.value, DOMAIN, unique_id
    )
    assert switch_entity_id is not None
    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR.value, DOMAIN, unique_id
        )
        is None
    )
    initial_state = hass.states.get(switch_entity_id)
    assert initial_state is not None and initial_state.state == STATE_UNAVAILABLE

    on_off_mode = point.characteristic("onOffMode")
    assert on_off_mode is not None
    on_off_mode.settable = True
    mock_onecta_client.get_gateway_devices.return_value = devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(Platform.SWITCH.value, DOMAIN, unique_id)
        == switch_entity_id
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR.value, DOMAIN, unique_id
        )
        is None
    )
    updated_state = hass.states.get(switch_entity_id)
    assert updated_state is not None and updated_state.state == "off"


def test_settable_climate_power_without_setpoint_has_switch_description() -> None:
    """Expose writable power as a switch when no climate entity owns it."""
    assert SWITCH_DESCRIPTIONS["onOffMode"].translation_key == "onoffmode"


def test_econo_mode_is_a_switch_without_a_climate_entity() -> None:
    """Keep econo mode exposed when a point has no climate preset entity."""
    point_without_temperature_control = ManagementPoint(
        embedded_id="point_without_temperature_control",
        management_point_type="climateControl",
        characteristics={
            "econoMode": Characteristic(
                value="off", settable=True, values=["on", "off"]
            )
        },
    )
    econo_mode = point_without_temperature_control.scalar_characteristic("econoMode")
    assert econo_mode is not None

    assert (
        scalar_platform_for_point(point_without_temperature_control, "econoMode")
        is Platform.SWITCH
    )

    main_zone = ManagementPoint(
        embedded_id="main_zone",
        management_point_type="climateControlMainZone",
        characteristics={
            "econoMode": Characteristic(
                value="off", settable=True, values=["on", "off"]
            )
        },
    )
    main_zone_econo_mode = main_zone.scalar_characteristic("econoMode")
    assert main_zone_econo_mode is not None
    assert scalar_platform_for_point(main_zone, "econoMode") is Platform.SWITCH

    device = _load_gateway_devices("climate_floorheatingairflow")[0]
    climate_point = device.management_points_by_type("climateControl")[0]
    climate_econo_mode = climate_point.scalar_characteristic("econoMode")
    assert climate_econo_mode is not None
    assert scalar_platform_for_point(climate_point, "econoMode") is None


def test_energy_description_key() -> None:
    """Return a key only when both the period and description are supported."""
    aggregate = next(
        aggregate
        for device in _load_gateway_devices("altherma")
        for point in device.management_points
        for aggregate in point.energy_aggregates
    )

    assert energy_description_key(aggregate) == "HeatingDailyElectricalConsumption"
    assert energy_description_key(replace(aggregate, period="quarter")) is None
    assert energy_description_key(replace(aggregate, source="future-source")) is None


async def test_air_purifier_offline_does_not_create_mode_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep purifier controls on their stable platforms when power is read-only."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    fan_unique_id = f"{device.id}_{point.embedded_id}_air_purifier"
    mode_sensor_unique_id = f"{device.id}_{point.embedded_id}_airPurificationMode"
    fan_entity_id = entity_registry.async_get_entity_id(
        Platform.FAN.value, DOMAIN, fan_unique_id
    )
    assert fan_entity_id is not None
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_sensor_unique_id
        )
        is None
    )

    offline_devices = deepcopy(_load_gateway_devices("mc80z"))
    offline_devices[0].cloud_connection.value = False
    offline_point = offline_devices[0].management_points_by_type("climateControl")[0]
    assert offline_point.air_purification is not None
    assert offline_point.air_purification.power is not None
    offline_point.air_purification.power.settable = False
    mock_onecta_client.get_gateway_devices.return_value = offline_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_sensor_unique_id
        )
        is None
    )
    fan_state = hass.states.get(fan_entity_id)
    assert fan_state is not None and fan_state.state == STATE_UNAVAILABLE

    read_only_devices = deepcopy(_load_gateway_devices("mc80z"))
    read_only_point = read_only_devices[0].management_points_by_type("climateControl")[
        0
    ]
    assert read_only_point.air_purification is not None
    assert read_only_point.air_purification.power is not None
    read_only_point.air_purification.power.settable = False
    mock_onecta_client.get_gateway_devices.return_value = read_only_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_sensor_unique_id
        )
        is None
    )
    fan_state = hass.states.get(fan_entity_id)
    assert fan_state is not None and fan_state.state == STATE_UNAVAILABLE

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("mc80z")
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_sensor_unique_id
        )
        is None
    )
    fan_state = hass.states.get(fan_entity_id)
    assert fan_state is not None and fan_state.state != STATE_UNAVAILABLE


async def test_read_only_air_purifier_keeps_fan_ownership_stable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Create the fan even when power is initially read-only."""
    read_only_devices = deepcopy(_load_gateway_devices("mc80z"))
    gateway = read_only_devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    assert point.air_purification is not None
    assert point.air_purification.power is not None
    point.air_purification.power.settable = False

    await _async_setup_fixture(
        hass,
        config_entry,
        "mc80z",
        gateway_devices=read_only_devices,
    )

    coordinator = config_entry.runtime_data
    fan_unique_id = f"{gateway.id}_{point.embedded_id}_air_purifier"
    mode_unique_id = f"{gateway.id}_{point.embedded_id}_airPurificationMode"
    fan_entity_id = entity_registry.async_get_entity_id(
        Platform.FAN.value, DOMAIN, fan_unique_id
    )
    assert fan_entity_id is not None
    fan_state = hass.states.get(fan_entity_id)
    assert fan_state is not None and fan_state.state == STATE_UNAVAILABLE
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_unique_id
        )
        is None
    )

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("mc80z")
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(Platform.FAN.value, DOMAIN, fan_unique_id)
        == fan_entity_id
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR.value, DOMAIN, mode_unique_id
        )
        is None
    )
    fan_state = hass.states.get(fan_entity_id)
    assert fan_state is not None and fan_state.state != STATE_UNAVAILABLE


async def _async_fire_coordinator_update(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance time until the coordinator's next scheduled update."""
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_offline_air_purifier_does_not_create_power_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Avoid a permanent scalar power entity during a purifier outage."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    power_unique_id = f"{device.id}_{point.embedded_id}_onOffMode"
    fan_entity_id = entity_registry.async_get_entity_id(
        Platform.FAN.value,
        DOMAIN,
        f"{device.id}_{point.embedded_id}_air_purifier",
    )
    assert fan_entity_id is not None

    offline_devices = deepcopy(_load_gateway_devices("mc80z"))
    offline_devices[0].cloud_connection.value = False
    offline_point = offline_devices[0].management_points_by_type("climateControl")[0]
    assert offline_point.air_purification is not None
    assert offline_point.air_purification.power is not None
    offline_point.air_purification.power.settable = False
    mock_onecta_client.get_gateway_devices.return_value = offline_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR.value, DOMAIN, power_unique_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH.value, DOMAIN, power_unique_id
        )
        is None
    )

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("mc80z")
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR.value, DOMAIN, power_unique_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH.value, DOMAIN, power_unique_id
        )
        is None
    )
    assert (fan_state := hass.states.get(fan_entity_id)) is not None
    assert fan_state.state != STATE_UNAVAILABLE


async def test_offline_gateway_reconnect_does_not_create_owned_scalar_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep the climate entity registered while its gateway is offline."""
    await _async_setup_fixture(hass, config_entry, "offlinedevice")
    coordinator = config_entry.runtime_data
    offline_devices = _load_gateway_devices("offlinedevice")
    device = offline_devices[0]
    point = device.management_points_by_type("climateControl")[0]
    owned_scalar_ids = (
        (Platform.BINARY_SENSOR, f"{device.id}_{point.embedded_id}_onOffMode"),
        (Platform.SENSOR, f"{device.id}_{point.embedded_id}_powerfulMode"),
    )

    for platform, unique_id in owned_scalar_ids:
        assert (
            entity_registry.async_get_entity_id(platform.value, DOMAIN, unique_id)
            is None
        )
    climate_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{device.id}_{point.embedded_id}_roomTemperature",
    )
    assert climate_entity_id is not None
    climate_state = hass.states.get(climate_entity_id)
    assert climate_state is not None
    assert climate_state.state == STATE_UNAVAILABLE

    online_devices = deepcopy(offline_devices)
    online_device = online_devices[0]
    online_device.cloud_connection.value = True
    online_point = online_device.management_points_by_type("climateControl")[0]
    assert online_point.on_off_mode is not None
    online_point.on_off_mode.settable = True
    powerful_mode = online_point.characteristic("powerfulMode")
    assert powerful_mode is not None
    powerful_mode.settable = True
    climate_control = online_point.climate_control
    assert climate_control is not None
    room_temperature = climate_control.setpoint("roomTemperature")
    assert room_temperature is not None
    room_temperature.settable = True

    mock_onecta_client.get_gateway_devices.return_value = online_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    for platform, unique_id in owned_scalar_ids:
        assert (
            entity_registry.async_get_entity_id(platform.value, DOMAIN, unique_id)
            is None
        )
    reconnected_climate_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{device.id}_{point.embedded_id}_roomTemperature",
    )
    assert reconnected_climate_entity_id == climate_entity_id
    reconnected_climate_state = hass.states.get(reconnected_climate_entity_id)
    assert reconnected_climate_state is not None
    assert reconnected_climate_state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("platform", "device_index", "management_point_type", "characteristic_name"),
    [
        pytest.param(
            Platform.SWITCH,
            1,
            "climateControl",
            "streamerMode",
            id="switch-streamerMode",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            1,
            "gateway",
            "ledEnabled",
            id="binary-sensor-ledEnabled",
        ),
        pytest.param(
            Platform.SENSOR,
            0,
            "gateway",
            "ipAddress",
            id="sensor-ipAddress",
        ),
    ],
)
async def test_missing_scalar_value_does_not_change_entity_topology(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    platform: Platform,
    device_index: int,
    management_point_type: str,
    characteristic_name: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep scalar entities registered when their current value is omitted."""
    cloud_devices = _load_gateway_devices("altherma")
    initial_devices = deepcopy(cloud_devices)
    device = initial_devices[device_index]
    point = device.management_points_by_type(management_point_type)[0]
    characteristic = point.scalar_characteristic(characteristic_name)
    assert characteristic is not None
    characteristic.value = None
    unique_id = f"{device.id}_{point.embedded_id}_{characteristic_name}"

    await _async_test_missing_value_does_not_schedule_reload(
        hass,
        config_entry,
        entity_registry,
        freezer,
        cloud_devices,
        initial_devices,
        platform,
        unique_id,
        mock_onecta_client,
    )


async def test_missing_firmware_version_does_not_change_entity_topology(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep firmware entities registered when their current version is omitted."""
    cloud_devices = _load_gateway_devices("dx4_firmwareavailable")
    initial_devices = deepcopy(cloud_devices)
    device = initial_devices[0]
    point = device.gateway_management_point
    assert point is not None
    point.firmware_version = None
    point.software_version = None

    await _async_test_missing_value_does_not_schedule_reload(
        hass,
        config_entry,
        entity_registry,
        freezer,
        cloud_devices,
        initial_devices,
        Platform.UPDATE,
        f"{device.id}_{point.embedded_id}_firmware",
        mock_onecta_client,
    )


async def _async_test_missing_value_does_not_schedule_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    cloud_devices: list[GatewayDevice],
    initial_devices: list[GatewayDevice],
    platform: Platform,
    unique_id: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Set up missing current data, then confirm a full response adds no topology."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.coordinator."
            "OnectaClient.get_gateway_devices",
            new=AsyncMock(return_value=initial_devices),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(platform.value, DOMAIN, unique_id)

    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.return_value = cloud_devices
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    schedule_reload.assert_not_called()


def _add_gateway(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Add a gateway with a distinct network identity."""
    gateway = deepcopy(devices[0])
    gateway.id = "new-gateway"
    gateway.gateway_management_point.characteristics.pop("macAddress", None)
    devices.append(gateway)
    point = gateway.management_points_by_type("climateControl")[0]
    return "climate", f"{gateway.id}_{point.embedded_id}_roomTemperature"


def _add_management_point(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Add a second independently controlled zone."""
    gateway = devices[0]
    point = deepcopy(gateway.management_points_by_type("climateControl")[0])
    point.embedded_id = "new-zone"
    gateway.management_points.append(point)
    return "climate", f"{gateway.id}_{point.embedded_id}_roomTemperature"


def _add_setpoint(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Advertise a leaving-water offset number on a climate management point."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    for operation in point.temperature_control.value.operation_modes.values():
        operation.setpoints["leavingWaterOffset"] = Setpoint(
            value=0, settable=True, min_value=-10, max_value=10
        )
    return "number", f"{gateway.id}_{point.embedded_id}_leavingWaterOffset"


def _add_boolean(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Expose a newly reported supported boolean characteristic."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.characteristics["ledEnabled"] = Characteristic(value=True)
    return "binary_sensor", f"{gateway.id}_{point.embedded_id}_ledEnabled"


def _add_scalar(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Expose a newly reported supported diagnostic value."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.characteristics["sgtin"] = Characteristic(value="diagnostic-id")
    return "sensor", f"{gateway.id}_{point.embedded_id}_sgtin"


def _add_sensory(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Expose a newly reported sensory-data field."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.sensory_data.value.room_humidity = Characteristic(value=50)
    return "sensor", f"{gateway.id}_{point.embedded_id}_sensory_data_roomHumidity"


def _add_schedule(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Expose schedules on an existing management point."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    source = next(
        point
        for device in _load_gateway_devices("schedule")
        for point in device.management_points
        if point.schedule_state is not None
    )
    point.schedule = deepcopy(source.schedule)
    return "select", f"{gateway.id}_{point.embedded_id}_schedule"


@pytest.mark.parametrize(
    ("add_capability", "disabled_by_default"),
    [
        (_add_gateway, False),
        (_add_management_point, False),
        (_add_setpoint, False),
        (_add_boolean, False),
        (_add_scalar, True),
        (_add_sensory, False),
        (_add_schedule, False),
    ],
)
async def test_poll_discovers_new_entities_without_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    add_capability: Callable[[list[GatewayDevice]], tuple[str, str]],
    disabled_by_default: bool,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Create a newly exposed entity on its platform after the next poll."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    domain, unique_id = add_capability(devices)
    assert entity_registry.async_get_entity_id(domain, DOMAIN, unique_id) is None

    mock_onecta_client.get_gateway_devices.return_value = devices
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is coordinator
    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    assert (hass.states.get(entity_id) is None) == disabled_by_default
    assert (
        entity_registry.async_get(entity_id).disabled_by is not None
    ) == disabled_by_default
    assert mock_onecta_client.get_gateway_devices.await_count == 1
    schedule_reload.assert_not_called()


async def test_multiple_new_capabilities_are_added_without_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Add capabilities from successive polls without reloading the entry."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    boolean_domain, boolean_unique_id = _add_boolean(devices)
    mock_onecta_client.get_gateway_devices.return_value = devices

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)
        updated_devices = deepcopy(devices)
        number_domain, number_unique_id = _add_setpoint(updated_devices)
        mock_onecta_client.get_gateway_devices.return_value = updated_devices
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity_registry.async_get_entity_id(
        boolean_domain, DOMAIN, boolean_unique_id
    )
    assert entity_registry.async_get_entity_id(number_domain, DOMAIN, number_unique_id)
    schedule_reload.assert_not_called()


async def test_discovering_second_climate_zone_moves_existing_entities_to_child(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep all zone entities together when a gateway gains a second zone."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    gateway = _load_gateway_devices("dry")[0]
    climate_point = gateway.management_points_by_type("climateControl")[0]
    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway.id), config_entry.entry_id
    )
    assert gateway_device is not None
    original_zone_prefix = f"{gateway.id}_{climate_point.embedded_id}_"
    original_zone_entities = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.unique_id.startswith(original_zone_prefix)
    ]
    assert original_zone_entities
    assert all(entry.device_id == gateway_device.id for entry in original_zone_entities)

    second_zone = deepcopy(climate_point)
    second_zone.embedded_id = "new-zone"
    second_zone.name = Characteristic(value="Second zone")
    gateway.management_points.append(second_zone)
    mock_onecta_client.get_gateway_devices.return_value = [gateway]

    await _async_fire_coordinator_update(hass, coordinator, freezer)

    original_child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway.id}_{climate_point.embedded_id}"), config_entry.entry_id
    )
    second_child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway.id}_{second_zone.embedded_id}"), config_entry.entry_id
    )
    assert original_child is not None
    assert second_child is not None
    assert original_child.parent_device_id == gateway_device.id
    assert second_child.parent_device_id == gateway_device.id
    updated_zone_entities = [
        entity_registry.async_get(entry.entity_id) for entry in original_zone_entities
    ]
    assert all(entry is not None for entry in updated_zone_entities)
    assert all(
        entry.device_id == original_child.id
        for entry in updated_zone_entities
        if entry is not None
    )

    new_climate_entity = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{gateway.id}_{second_zone.embedded_id}_roomTemperature",
    )
    assert new_climate_entity is not None
    new_climate_entry = entity_registry.async_get(new_climate_entity)
    assert new_climate_entry is not None
    assert new_climate_entry.device_id == second_child.id


async def test_climate_zone_rename_updates_child_device_name(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Refresh a zone child device name when Daikin renames the zone."""
    gateway = _load_gateway_devices("dry")[0]
    first_zone = gateway.management_points_by_type("climateControl")[0]
    second_zone = deepcopy(first_zone)
    second_zone.embedded_id = "second-zone"
    second_zone.name = Characteristic(value="Second zone")
    gateway.management_points.append(second_zone)
    await _async_setup_fixture(hass, config_entry, "dry", gateway_devices=[gateway])

    coordinator = config_entry.runtime_data
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway.id}_{first_zone.embedded_id}"), config_entry.entry_id
    )
    assert child is not None
    assert child.name == first_zone.name.value

    renamed_gateway = deepcopy(gateway)
    renamed_point = renamed_gateway.management_points_by_type("climateControl")[0]
    renamed_point.name = Characteristic(value="Renamed zone")
    mock_onecta_client.get_gateway_devices.return_value = [renamed_gateway]
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    renamed_child = device_registry.async_get(child.id)
    assert renamed_child is not None
    assert renamed_child.name == "Renamed zone"


async def test_discovering_single_climate_zone_moves_entities_back_to_gateway(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Move a zone back to the gateway and allow removing its empty child."""
    gateway = _load_gateway_devices("dry")[0]
    first_zone = gateway.management_points_by_type("climateControl")[0]
    second_zone = deepcopy(first_zone)
    second_zone.embedded_id = "new-zone"
    second_zone.name = Characteristic(value="Second zone")
    gateway.management_points.append(second_zone)

    await _async_setup_fixture(hass, config_entry, "dry", gateway_devices=[gateway])
    coordinator = config_entry.runtime_data
    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway.id), config_entry.entry_id
    )
    first_zone_child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway.id}_{first_zone.embedded_id}"), config_entry.entry_id
    )
    assert gateway_entry is not None
    assert first_zone_child is not None

    first_zone_prefix = f"{gateway.id}_{first_zone.embedded_id}_"
    first_zone_entities = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.unique_id.startswith(first_zone_prefix)
    ]
    assert first_zone_entities
    assert all(entry.device_id == first_zone_child.id for entry in first_zone_entities)

    single_zone_gateway = deepcopy(gateway)
    single_zone_gateway.management_points = [
        point
        for point in single_zone_gateway.management_points
        if point.embedded_id != second_zone.embedded_id
    ]
    mock_onecta_client.get_gateway_devices.return_value = [single_zone_gateway]
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    moved_entities = [
        entity_registry.async_get(entry.entity_id) for entry in first_zone_entities
    ]
    assert all(entry is not None for entry in moved_entities)
    assert all(
        entry.device_id == gateway_entry.id
        for entry in moved_entities
        if entry is not None
    )
    assert not er.async_entries_for_device(
        entity_registry, first_zone_child.id, include_disabled_entities=True
    )
    assert await async_remove_config_entry_device(hass, config_entry, first_zone_child)


async def test_disabled_discovered_entity_is_recreated_after_registry_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Recreate an aborted disabled entity when its registry entry is removed."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    domain, unique_id = _add_scalar(devices)
    mock_onecta_client.get_gateway_devices.return_value = devices

    await _async_fire_coordinator_update(hass, coordinator, freezer)

    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled
    entity_registry.async_remove(entity_id)

    await _async_fire_coordinator_update(hass, coordinator, freezer)

    recreated_entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert recreated_entity_id is not None
    assert entity_registry.async_get(recreated_entity_id).disabled


async def test_binary_key_with_additional_values_is_not_a_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not create a text sensor when a binary key gains an enum option."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.characteristics["ledEnabled"] = Characteristic(
        value="on", settable=False, values=["on", "off"]
    )
    unique_id = f"{gateway.id}_{point.embedded_id}_ledEnabled"
    mock_onecta_client.get_gateway_devices.return_value = devices
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

        assert entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        enum_devices = deepcopy(devices)
        enum_devices[0].management_points_by_type("climateControl")[0].characteristics[
            "ledEnabled"
        ].values = ["on", "off", "auto"]
        mock_onecta_client.get_gateway_devices.return_value = enum_devices
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None
    assert coordinator is config_entry.runtime_data
    schedule_reload.assert_not_called()


async def test_state_changes_do_not_reload_platforms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Ordinary temperature changes are not new entity capabilities."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    point = devices[0].management_points_by_type("climateControl")[0]
    next(iter(point.temperature_control.value.operation_modes.values())).setpoints[
        "roomTemperature"
    ].value += 1
    mock_onecta_client.get_gateway_devices.return_value = devices

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    schedule_reload.assert_not_called()


def _remove_purifier(point: ManagementPoint) -> None:
    """Remove the characteristic that identifies air purification."""
    point.characteristics.pop("airPurificationMode")


def _remove_purifier_power(point: ManagementPoint) -> None:
    """Remove the purifier's power characteristic."""
    point.on_off_mode = None


def _make_purifier_read_only(point: ManagementPoint) -> None:
    """Remove the purifier's writable power capability."""
    assert point.on_off_mode is not None
    point.on_off_mode.settable = False


def _remove_schedule(point: ManagementPoint) -> None:
    """Remove all schedule data from the management point."""
    point.schedule = None


def _remove_switch(point: ManagementPoint) -> None:
    """Remove an independently switchable characteristic."""
    point.characteristics.pop("streamerMode")


def _make_switch_read_only(point: ManagementPoint) -> None:
    """Remove a switch's writable capability."""
    point.characteristics["streamerMode"].settable = False


@pytest.mark.parametrize(
    ("fixture", "domain", "suffix", "remove_capability"),
    [
        pytest.param("mc80z", "fan", "air_purifier", _remove_purifier, id="purifier"),
        pytest.param(
            "mc80z",
            "fan",
            "air_purifier",
            _remove_purifier_power,
            id="purifier_power",
        ),
        pytest.param(
            "mc80z",
            "fan",
            "air_purifier",
            _make_purifier_read_only,
            id="purifier_read_only",
        ),
        pytest.param("schedule", "select", "schedule", _remove_schedule, id="schedule"),
        pytest.param("altherma", "switch", "streamerMode", _remove_switch, id="switch"),
        pytest.param(
            "altherma",
            "switch",
            "streamerMode",
            _make_switch_read_only,
            id="switch_read_only",
        ),
    ],
)
async def test_removed_controls_become_unavailable_and_recover(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    fixture: str,
    domain: str,
    suffix: str,
    remove_capability: Callable[[ManagementPoint], None],
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Retain an entity's identity when its control disappears and returns."""
    await _async_setup_fixture(hass, config_entry, fixture)
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices(fixture)
    gateway, point, entity_id = next(
        (gateway, point, entity_id)
        for gateway in devices
        for point in gateway.management_points
        if (
            entity_id := entity_registry.async_get_entity_id(
                domain, DOMAIN, f"{gateway.id}_{point.embedded_id}_{suffix}"
            )
        )
        is not None
    )
    initial_state = hass.states.get(entity_id)
    assert initial_state is not None
    assert initial_state.state != STATE_UNAVAILABLE
    registry_entry = entity_registry.async_get(entity_id)
    restored_devices = deepcopy(devices)
    remove_capability(point)
    mock_onecta_client.get_gateway_devices.return_value = devices

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

        assert coordinator.data[gateway.id].available
        assert (
            coordinator.data[gateway.id].management_point(point.embedded_id) is not None
        )
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert entity_registry.async_get(entity_id).id == registry_entry.id
        assert (
            entity_registry.async_get(entity_id).unique_id == registry_entry.unique_id
        )
        schedule_reload.assert_not_called()

        mock_onecta_client.get_gateway_devices.return_value = restored_devices
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert hass.states.get(entity_id).state == initial_state.state
    assert entity_registry.async_get(entity_id).id == registry_entry.id
    assert entity_registry.async_get(entity_id).unique_id == registry_entry.unique_id
    schedule_reload.assert_not_called()
