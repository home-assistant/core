"""Test telemetry discovery and preservation with synthetic device updates."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .conftest import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SITE,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

DEVICE = {
    "device_id": "telemetry-device",
    "mac": "00:00:00:00:01:01",
    "name": "Device",
    "model": "USP-PDU-Pro",
    "type": "usw",
    "version": "7.0.0",
    "state": 1,
}

TELEMETRY_CASES = [
    pytest.param(
        "outlet_ac_power_budget",
        "1875",
        ("ac_power_budget",),
        ("1875",),
        id="pdu-budget",
    ),
    pytest.param(
        "system-stats",
        {"cpu": "5.8", "mem": "31.1"},
        ("cpu_utilization", "memory_utilization"),
        ("5.8", "31.1"),
        id="system-stats",
    ),
    pytest.param(
        "vbms_table",
        {"battpool": {"device_total_power_output": 42.5}},
        ("output_power",),
        ("42.5",),
        id="ups",
    ),
    pytest.param(
        "uptime_stats",
        {"WAN": {"monitors": [{"target": "google.com", "latency_average": 53}]}},
        ("google_wan_latency",),
        ("53",),
        id="wan",
    ),
    pytest.param(
        "temperatures",
        [{"name": "CPU", "type": "cpu", "value": 66}],
        ("cpu_temperature",),
        ("66",),
        id="temperature",
    ),
    pytest.param(
        "uplink",
        {"uplink_mac": "00:00:00:00:02:02"},
        ("uplink_mac",),
        ("00:00:00:00:02:02",),
        id="uplink",
    ),
]


@pytest.fixture
def device_payload(
    field: str, telemetry: dict[str, Any] | list[dict[str, Any]] | str | bool
) -> list[dict[str, Any]]:
    """Build synthetic telemetry using the controller's existing field shapes."""
    models = {
        "vbms_table": {"model": "UPS-2U-Pro"},
        "uptime_stats": {"model": "UCG-Fiber", "type": "udm"},
        "temperatures": {"model": "USW-Pro-24-PoE"},
    }
    return [{**DEVICE, **models.get(field, {}), field: deepcopy(telemetry)}]


@pytest.mark.parametrize(("field", "telemetry", "sensors", "values"), TELEMETRY_CASES)
@pytest.mark.parametrize(
    "gap", [pytest.param((), id="absent"), pytest.param((None,), id="null")]
)
async def test_telemetry_gap_and_reload(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_message: WebsocketMessageMock,
    mock_websocket_state: WebsocketStateManager,
    device_payload: list[dict[str, Any]],
    field: str,
    sensors: tuple[str, ...],
    values: tuple[str, ...],
    gap: tuple[None, ...],
) -> None:
    """Keep registered sensors through missing telemetry, reload and recovery."""
    original = deepcopy(device_payload[0])
    entries = {
        f"sensor.device_{sensor}": entity_registry.async_update_entity(
            f"sensor.device_{sensor}",
            disabled_by=None,
            name="Custom telemetry",
            icon="mdi:chart-line",
        )
        for sensor in sensors
    }
    # Reload also enables diagnostic entities that default to disabled.
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    for entity_id, value in zip(entries, values, strict=True):
        assert hass.states.get(entity_id).state == value
    entries = {entity_id: entity_registry.async_get(entity_id) for entity_id in entries}

    await mock_websocket_state.disconnect()
    for entity_id in entries:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    await mock_websocket_state.reconnect()

    device_payload[0].pop(field)
    for reading in gap:
        device_payload[0][field] = reading
    mock_websocket_message(message=MessageKey.DEVICE, data=device_payload[0])
    await hass.async_block_till_done()
    for entity_id, entry in entries.items():
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
        assert entity_registry.async_get(entity_id) == entry

    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    for entity_id, entry in entries.items():
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
        assert entity_registry.async_get(entity_id) == entry

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    for entity_id, value in zip(entries, values, strict=True):
        assert hass.states.get(entity_id).state == value
        assert entity_registry.async_get(entity_id) == entries[entity_id]

    config_entry_setup.runtime_data.api.devices.remove_item(original)
    await hass.async_block_till_done()
    for entity_id in entries:
        assert hass.states.get(entity_id) is None
        assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(("field", "telemetry", "sensors", "values"), TELEMETRY_CASES)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "initial_readings",
    [pytest.param((), id="absent"), pytest.param((None,), id="null")],
)
async def test_telemetry_late_discovery(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    field: str,
    sensors: tuple[str, ...],
    values: tuple[str, ...],
    initial_readings: tuple[None, ...],
) -> None:
    """Require initial evidence and discover restored data on ordinary updates."""
    original = deepcopy(device_payload[0])
    device_payload[0].pop(field)
    for reading in initial_readings:
        device_payload[0][field] = reading
    await config_entry_factory()
    for sensor in sensors:
        assert entity_registry.async_get(f"sensor.device_{sensor}") is None

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    for sensor, value in zip(sensors, values, strict=True):
        entity_id = f"sensor.device_{sensor}"
        assert entity_registry.async_get(entity_id) is not None
        assert hass.states.get(entity_id).state == value


@pytest.mark.parametrize(
    ("model", "device_type"),
    [
        ("USP-PDU-Pro", "usw"),
        ("UPS-2U-Pro", "usw"),
        ("U7-Pro", "uap"),
        ("USW-Aggregation", "usw"),
        ("US-8", "usw"),
        ("U5G Backup", "ubb"),
    ],
)
@pytest.mark.parametrize(
    "missing_stats",
    [
        pytest.param({}, id="missing-table"),
        pytest.param({"system-stats": None}, id="null-table"),
        pytest.param({"system-stats": {}}, id="missing-fields"),
        pytest.param({"system-stats": {"cpu": None, "mem": None}}, id="null-fields"),
        pytest.param({"system-stats": {"cpu": "", "mem": ""}}, id="empty-fields"),
    ],
)
@pytest.mark.parametrize(
    ("field", "telemetry", "sensors", "values"), [TELEMETRY_CASES[1]]
)
async def test_system_stats_telemetry(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    model: str,
    device_type: str,
    missing_stats: dict[str, Any],
    sensors: tuple[str, ...],
    values: tuple[str, ...],
) -> None:
    """Retain CPU/memory across representative models and accept initial zero."""
    device = device_payload[0]
    device.update(model=model, type=device_type)
    device["system-stats"] = {"cpu": 0, "mem": 0}
    await config_entry_factory()
    entity_ids = tuple(f"sensor.device_{sensor}" for sensor in sensors)
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == "0"

    gap = deepcopy(device)
    gap.pop("system-stats")
    gap.update(missing_stats)
    mock_websocket_message(message=MessageKey.DEVICE, data=gap)
    await hass.async_block_till_done()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
        assert entity_registry.async_get(entity_id) is not None

    mock_websocket_message(message=MessageKey.DEVICE, data=device)
    await hass.async_block_till_done()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == "0"


@pytest.mark.parametrize(
    ("field", "telemetry", "sensors", "values"), [TELEMETRY_CASES[0]]
)
@pytest.mark.parametrize(
    "gap",
    [
        pytest.param({}, id="missing"),
        pytest.param(
            {"outlet_ac_power_budget": None, "outlet_ac_power_consumption": None},
            id="null",
        ),
    ],
)
async def test_pdu_aggregate_power(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    sensors: tuple[str, ...],
    values: tuple[str, ...],
    gap: dict[str, None],
) -> None:
    """Keep both PDU aggregate sensors and valid zero readings."""
    device = device_payload[0]
    device.update(outlet_ac_power_budget=0, outlet_ac_power_consumption=0)
    await config_entry_factory()
    entity_ids = ("sensor.device_ac_power_budget", "sensor.device_ac_power_consumption")
    entries = {
        entity_id: entity_registry.async_get(entity_id) for entity_id in entity_ids
    }
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == "0"

    missing = {**DEVICE, **gap}
    mock_websocket_message(message=MessageKey.DEVICE, data=missing)
    await hass.async_block_till_done()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
        assert entity_registry.async_get(entity_id) == entries[entity_id]

    mock_websocket_message(message=MessageKey.DEVICE, data=device)
    await hass.async_block_till_done()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == "0"


@pytest.mark.parametrize(("field", "telemetry"), [("has_temperature", True)])
@pytest.mark.parametrize(
    "gap",
    [
        pytest.param({}, id="missing"),
        pytest.param({"has_temperature": None, "general_temperature": None}, id="null"),
    ],
)
async def test_general_temperature_capability(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    gap: dict[str, None],
) -> None:
    """Distinguish incomplete capability data from explicit loss of support."""
    original = {**device_payload[0], "general_temperature": 0}
    device_payload[0] = original
    await config_entry_factory()
    entity_id = "sensor.device_temperature"
    assert hass.states.get(entity_id).state == "0"
    entry = entity_registry.async_get(entity_id)

    mock_websocket_message(message=MessageKey.DEVICE, data={**DEVICE, **gap})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert entity_registry.async_get(entity_id) == entry

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "0"

    mock_websocket_message(
        message=MessageKey.DEVICE, data={**original, "has_temperature": False}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(
    ("field", "telemetry"),
    [("port_table", [{"port_idx": 1, "name": "Port 1", "speed": 1000}])],
)
@pytest.mark.parametrize(
    ("reading", "expected"),
    [
        pytest.param({}, STATE_UNKNOWN, id="absent"),
        pytest.param({"speed": None}, STATE_UNKNOWN, id="null"),
        pytest.param({"speed": 0}, "0", id="zero"),
    ],
)
async def test_port_speed_telemetry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    reading: dict[str, int | None],
    expected: str,
) -> None:
    """Restore a customized port sensor while link telemetry is missing."""
    original = deepcopy(device_payload[0])
    config_entry = await config_entry_factory()
    entity_id = "sensor.custom_port_speed"
    entity_registry.async_update_entity(
        "sensor.device_port_1_link_speed", new_entity_id=entity_id, disabled_by=None
    )
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "1000"
    entry = entity_registry.async_get(entity_id)

    device_payload[0]["port_table"][0].pop("speed")
    device_payload[0]["port_table"][0].update(reading)
    mock_websocket_message(message=MessageKey.DEVICE, data=device_payload[0])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert entity_registry.async_get(entity_id) == entry

    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert entity_registry.async_get(entity_id) == entry

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "1000"
    assert entity_registry.async_get(entity_id) == entry


@pytest.mark.parametrize(
    ("field", "telemetry"),
    [("outlet_ac_power_budget", "1875")],
)
async def test_telemetry_registry_scope(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    device_payload: list[dict[str, Any]],
) -> None:
    """Do not use another config entry's registry as capability evidence."""
    other_entry = MockConfigEntry(domain="unifi")
    other_entry.add_to_hass(hass)
    registered = entity_registry.async_get_or_create(
        "sensor",
        "unifi",
        f"ac_power_budget-{DEVICE['mac']}",
        suggested_object_id="other_device_power_budget",
        config_entry=other_entry,
    )
    device_payload[0].pop("outlet_ac_power_budget")
    await config_entry_factory()
    assert entity_registry.async_get(registered.entity_id) == registered
    assert hass.states.get("sensor.device_ac_power_budget") is None


@pytest.mark.parametrize(
    ("field", "telemetry", "sensor", "capability_field", "value_field"),
    [
        pytest.param(
            "outlet_table",
            [
                {
                    "index": 1,
                    "name": "Outlet 1",
                    "has_metering": True,
                    "relay_state": True,
                    "outlet_power": "2.5",
                }
            ],
            "outlet_1_outlet_power",
            "has_metering",
            "outlet_power",
            id="outlet-metering",
        ),
        pytest.param(
            "port_table",
            [
                {
                    "port_idx": 1,
                    "name": "Port 1",
                    "port_poe": True,
                    "poe_mode": "auto",
                    "poe_power": "2.5",
                }
            ],
            "port_1_poe_power",
            "port_poe",
            "poe_power",
            id="poe",
        ),
    ],
)
async def test_subdevice_capability_changes(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    field: str,
    sensor: str,
    capability_field: str,
    value_field: str,
) -> None:
    """Preserve incomplete telemetry but respect explicit capability removal."""
    original = deepcopy(device_payload[0])
    config_entry = await config_entry_factory()
    entity_id = f"sensor.device_{sensor}"
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "2.5"
    entry = entity_registry.async_get(entity_id)

    incomplete = deepcopy(original)
    incomplete[field][0].pop(capability_field)
    incomplete[field][0].pop(value_field)
    mock_websocket_message(message=MessageKey.DEVICE, data=incomplete)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert entity_registry.async_get(entity_id) == entry

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "2.5"

    unsupported = deepcopy(original)
    unsupported[field][0][capability_field] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=unsupported)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(
    ("field", "telemetry"),
    [
        (
            "outlet_table",
            [
                {
                    "index": 1,
                    "name": "Outlet 1",
                    "has_metering": True,
                    "relay_state": True,
                    "outlet_power": "2.5",
                }
            ],
        )
    ],
)
@pytest.mark.parametrize(
    ("reading", "expected"),
    [
        pytest.param({}, STATE_UNKNOWN, id="missing-relay"),
        pytest.param({"relay_state": None}, STATE_UNKNOWN, id="null-relay"),
        pytest.param({"relay_state": False}, "0", id="relay-off"),
        pytest.param({"relay_state": True}, "2.5", id="relay-on"),
        pytest.param({"relay_state": True, "outlet_power": 0}, "0", id="zero-power"),
        pytest.param(
            {"relay_state": True, "outlet_power": None},
            STATE_UNKNOWN,
            id="null-power",
        ),
    ],
)
async def test_outlet_relay_telemetry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    reading: dict[str, bool | int | None],
    expected: str,
) -> None:
    """Clear incomplete outlet readings without mistaking null for relay-off."""
    original = deepcopy(device_payload[0])
    entity_id = "sensor.device_outlet_1_outlet_power"
    entry = entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id).state == "2.5"

    device_payload[0]["outlet_table"][0].pop("relay_state")
    device_payload[0]["outlet_table"][0].update(reading)
    mock_websocket_message(message=MessageKey.DEVICE, data=device_payload[0])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert entity_registry.async_get(entity_id) == entry

    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert entity_registry.async_get(entity_id) == entry

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "2.5"
    assert entity_registry.async_get(entity_id) == entry


@pytest.mark.parametrize(("field", "telemetry", "sensors", "values"), TELEMETRY_CASES)
async def test_user_disabled_telemetry_sensor(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    field: str,
    sensors: tuple[str, ...],
    values: tuple[str, ...],
) -> None:
    """Keep user-disabled entities disabled through gap reloads and recovery."""
    original = deepcopy(device_payload[0])
    entries = {
        f"sensor.device_{sensor}": entity_registry.async_update_entity(
            f"sensor.device_{sensor}",
            disabled_by=RegistryEntryDisabler.USER,
            name="Custom disabled telemetry",
        )
        for sensor in sensors
    }
    device_payload[0].pop(field)
    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    for entity_id, entry in entries.items():
        assert entity_registry.async_get(entity_id) == entry
        assert hass.states.get(entity_id) is None

    mock_websocket_message(message=MessageKey.DEVICE, data=original)
    await hass.async_block_till_done()
    for entity_id, entry in entries.items():
        assert entity_registry.async_get(entity_id) == entry
        assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(("field", "telemetry", "sensors", "values"), TELEMETRY_CASES)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_update_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    device_payload: list[dict[str, Any]],
    sensors: tuple[str, ...],
    values: tuple[str, ...],
) -> None:
    """Keep telemetry sensors unavailable during failed device refreshes."""
    entries = {
        f"sensor.device_{sensor}": entity_registry.async_get(f"sensor.device_{sensor}")
        for sensor in sensors
    }
    coordinator = (
        config_entry_setup.runtime_data.entity_loader.get_data_update_coordinator(
            config_entry_setup.runtime_data.api.devices
        )
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"https://{DEFAULT_HOST}:{DEFAULT_PORT}/api/s/{DEFAULT_SITE}/stat/device",
        status=503,
    )
    # Device coordinators use WebSocket updates and have no polling timer.
    # pylint: disable-next=home-assistant-tests-coordinator-async-refresh
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False
    for entity_id, entry in entries.items():
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert entity_registry.async_get(entity_id) == entry

    aioclient_mock.clear_requests()
    mock_requests()
    # pylint: disable-next=home-assistant-tests-coordinator-async-refresh
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True
    for entity_id, value in zip(entries, values, strict=True):
        assert hass.states.get(entity_id).state == value
        assert entity_registry.async_get(entity_id) == entries[entity_id]


@pytest.mark.parametrize(
    ("field", "telemetry", "sensor"),
    [
        pytest.param(
            "outlet_table",
            [
                {
                    "index": 1,
                    "name": "Outlet 1",
                    "has_metering": True,
                    "relay_state": True,
                    "outlet_power": "2.5",
                }
            ],
            "outlet_1_outlet_power",
            id="outlet",
        ),
        pytest.param(
            "port_table",
            [{"port_idx": 1, "name": "Port 1", "speed": 1000}],
            "port_1_link_speed",
            id="port",
        ),
    ],
)
@pytest.mark.parametrize(
    "tables",
    [pytest.param((), id="missing-table"), pytest.param(([],), id="empty-table")],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subdevice_table_library_boundary(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    field: str,
    sensor: str,
    tables: tuple[list[dict[str, Any]], ...],
) -> None:
    """Document aiounifi retaining old subdevices when whole tables disappear."""
    original = deepcopy(device_payload[0])
    entity_id = f"sensor.device_{sensor}"
    state = hass.states.get(entity_id).state
    entry = entity_registry.async_get(entity_id)

    missing = deepcopy(original)
    missing.pop(field)
    for table in tables:
        missing[field] = table
    mock_websocket_message(message=MessageKey.DEVICE, data=missing)
    await hass.async_block_till_done()
    # The library retains the last subdevice object; Core cannot clear its fields.
    assert hass.states.get(entity_id).state == state
    assert entity_registry.async_get(entity_id) == entry

    config_entry_setup.runtime_data.api.devices.remove_item(original)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(entity_id) is None
