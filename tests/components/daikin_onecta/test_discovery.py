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

from homeassistant.components.daikin_onecta import OnectaDataUpdateCoordinator
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.discovery import (
    energy_description_key,
    scalar_platform,
)
from homeassistant.components.daikin_onecta.entity_metadata import (
    BINARY_SENSOR_KEYS,
    SENSOR_KEYS,
    SWITCH_KEYS,
    UPDATE_KEYS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_ACCESS_TOKEN, MockOnectaClient
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


def test_sensor_keys_exclude_other_platform_keys() -> None:
    """Never create value sensors for binary, switch, update, or select keys."""
    assert SENSOR_KEYS.isdisjoint(BINARY_SENSOR_KEYS | SWITCH_KEYS | UPDATE_KEYS)
    assert "schedule" not in SENSOR_KEYS


@pytest.mark.parametrize(
    ("name", "characteristic", "management_point_type", "expected"),
    [
        pytest.param(
            "econoMode",
            Characteristic(value="on", settable=True, values=["on", "off"]),
            "climateControl",
            Platform.SWITCH,
            id="writable-on-off-switch",
        ),
        pytest.param(
            "ledEnabled",
            Characteristic(value="on", settable=True, values=["on", "off"]),
            "climateControl",
            None,
            id="writable-on-off-without-switch-description",
        ),
        pytest.param(
            "ledEnabled",
            Characteristic(value="on", values=["on", "off"]),
            "climateControl",
            Platform.BINARY_SENSOR,
            id="read-only-on-off-binary-sensor",
        ),
        pytest.param(
            "ledEnabled",
            Characteristic(value="on"),
            "climateControl",
            Platform.BINARY_SENSOR,
            id="binary-sensor-without-values",
        ),
        pytest.param(
            "ledEnabled",
            Characteristic(value="on", values=["on", "off", "auto"]),
            "climateControl",
            None,
            id="read-only-on-off-with-additional-value",
        ),
        pytest.param(
            "operationMode",
            Characteristic(value="heating"),
            "climateControl",
            None,
            id="control-operation-mode",
        ),
        pytest.param(
            "airPurificationMode",
            Characteristic(value="autoFan"),
            "climateControl",
            None,
            id="air-purification-mode-is-a-fan-preset",
        ),
        pytest.param(
            "operationMode",
            Characteristic(value="heating"),
            "outdoorUnit",
            Platform.SENSOR,
            id="non-control-operation-mode",
        ),
        pytest.param(
            "futureCharacteristic",
            Characteristic(value="unknown"),
            "climateControl",
            None,
            id="unknown-characteristic",
        ),
    ],
)
def test_scalar_platform(
    name: str,
    characteristic: Characteristic,
    management_point_type: str,
    expected: Platform | None,
) -> None:
    """Classify supported scalar characteristics consistently."""
    assert scalar_platform(name, characteristic, management_point_type) is expected


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


async def _async_fire_coordinator_update(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance time until the coordinator's next scheduled update."""
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("platform", "device_index", "management_point_type", "characteristic_name"),
    [
        pytest.param(
            Platform.SWITCH,
            1,
            "climateControl",
            "econoMode",
            id="switch-econoMode",
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
    )


async def test_missing_firmware_version_does_not_change_entity_topology(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep firmware entities registered when their current version is omitted."""
    cloud_devices = _load_gateway_devices("altherma")
    initial_devices = deepcopy(cloud_devices)
    device = initial_devices[0]
    point = device.management_points_by_type("indoorUnitHydro")[0]
    assert point.software_version is not None
    point.software_version.value = None

    await _async_test_missing_value_does_not_schedule_reload(
        hass,
        config_entry,
        entity_registry,
        freezer,
        cloud_devices,
        initial_devices,
        Platform.UPDATE,
        f"{device.id}_{point.embedded_id}_firmware",
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
) -> None:
    """Set up missing current data, then confirm a full response adds no topology."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator."
            "async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
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
    coordinator.client.get_gateway_devices = AsyncMock(return_value=cloud_devices)
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
    """Advertise a new target on an existing climate management point."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    for operation in point.temperature_control.value.operation_modes.values():
        operation.setpoints["leavingWaterOffset"] = Setpoint(
            value=0, settable=True, min_value=-10, max_value=10
        )
    return "climate", f"{gateway.id}_{point.embedded_id}_leavingWaterOffset"


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


def _add_firmware(devices: list[GatewayDevice]) -> tuple[str, str]:
    """Expose installed firmware on an existing management point."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.software_version = Characteristic(value="1.0")
    return "update", f"{gateway.id}_{point.embedded_id}_firmware"


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
        (_add_firmware, False),
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
        climate_domain, climate_unique_id = _add_setpoint(updated_devices)
        mock_onecta_client.get_gateway_devices.return_value = updated_devices
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity_registry.async_get_entity_id(
        boolean_domain, DOMAIN, boolean_unique_id
    )
    assert entity_registry.async_get_entity_id(
        climate_domain, DOMAIN, climate_unique_id
    )
    schedule_reload.assert_not_called()


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
    point.characteristics.pop("econoMode")


def _make_switch_read_only(point: ManagementPoint) -> None:
    """Remove a switch's writable capability."""
    point.characteristics["econoMode"].settable = False


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
        pytest.param("altherma", "switch", "econoMode", _remove_switch, id="switch"),
        pytest.param(
            "altherma",
            "switch",
            "econoMode",
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
