"""Tests for runtime discovery of new gateways and supported capabilities."""

from collections.abc import Callable
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import (
    Characteristic,
    GatewayDevice,
    ManagementPoint,
    Setpoint,
)
import pytest

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_ACCESS_TOKEN
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

from tests.common import MockConfigEntry


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
    """Expose a newly reported boolean characteristic."""
    gateway = devices[0]
    point = gateway.management_points_by_type("climateControl")[0]
    point.characteristics["newBoolean"] = Characteristic(value=True)
    return "binary_sensor", f"{gateway.id}_{point.embedded_id}_newBoolean"


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
async def test_poll_discovers_new_entities_through_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    add_capability: Callable[[list[GatewayDevice]], tuple[str, str]],
    disabled_by_default: bool,
) -> None:
    """Poll, reload, and actually create a newly exposed platform entity."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    domain, unique_id = add_capability(devices)
    assert entity_registry.async_get_entity_id(domain, DOMAIN, unique_id) is None

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            return_value=FAKE_ACCESS_TOKEN,
        ),
        patch(
            "homeassistant.components.daikin_onecta.daikin_api.OnectaClient.get_gateway_devices",
            return_value=devices,
        ) as get_gateways,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not coordinator
    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    assert (hass.states.get(entity_id) is None) == disabled_by_default
    assert (
        entity_registry.async_get(entity_id).disabled_by is not None
    ) == disabled_by_default
    assert get_gateways.await_count == 2


async def test_pending_discovery_reload_is_not_scheduled_twice(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Only schedule one reload when another capability appears while it is pending."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    _add_boolean(devices)
    coordinator.api.get_cloud_device_details = AsyncMock(return_value=devices)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await coordinator.async_refresh()
        updated_devices = deepcopy(devices)
        _add_setpoint(updated_devices)
        coordinator.api.get_cloud_device_details.return_value = updated_devices
        await coordinator.async_refresh()

    schedule_reload.assert_called_once_with(config_entry.entry_id)


async def test_state_changes_do_not_reload_platforms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Ordinary temperature changes are not new entity capabilities."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    devices = _load_gateway_devices("minimal_data")
    point = devices[0].management_points_by_type("climateControl")[0]
    next(iter(point.temperature_control.value.operation_modes.values())).setpoints[
        "roomTemperature"
    ].value += 1
    coordinator.api.get_cloud_device_details = AsyncMock(return_value=devices)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await coordinator.async_refresh()

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
    ("fixture", "domain", "suffix", "remove_capability", "removal_reload_count"),
    [
        pytest.param(
            "mc80z", "fan", "air_purifier", _remove_purifier, 0, id="purifier"
        ),
        pytest.param(
            "mc80z",
            "fan",
            "air_purifier",
            _remove_purifier_power,
            0,
            id="purifier_power",
        ),
        pytest.param(
            "mc80z",
            "fan",
            "air_purifier",
            _make_purifier_read_only,
            1,
            id="purifier_read_only",
        ),
        pytest.param(
            "schedule", "select", "schedule", _remove_schedule, 0, id="schedule"
        ),
        pytest.param("altherma", "switch", "econoMode", _remove_switch, 0, id="switch"),
        pytest.param(
            "altherma",
            "switch",
            "econoMode",
            _make_switch_read_only,
            1,
            id="switch_read_only",
        ),
    ],
)
async def test_removed_controls_become_unavailable_and_recover(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    domain: str,
    suffix: str,
    remove_capability: Callable[[ManagementPoint], None],
    removal_reload_count: int,
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
    coordinator.api.get_cloud_device_details = AsyncMock(return_value=devices)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await coordinator.async_refresh()

        assert coordinator.data[gateway.id].available
        assert (
            coordinator.data[gateway.id].management_point(point.embedded_id) is not None
        )
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert entity_registry.async_get(entity_id).id == registry_entry.id
        assert (
            entity_registry.async_get(entity_id).unique_id == registry_entry.unique_id
        )
        assert schedule_reload.call_count == removal_reload_count

        coordinator.api.get_cloud_device_details.return_value = restored_devices
        await coordinator.async_refresh()

    assert hass.states.get(entity_id).state == initial_state.state
    assert entity_registry.async_get(entity_id).id == registry_entry.id
    assert entity_registry.async_get(entity_id).unique_id == registry_entry.unique_id
    schedule_reload.assert_called_once_with(config_entry.entry_id)
