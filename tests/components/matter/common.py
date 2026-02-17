"""Provide common test tools."""

from __future__ import annotations

from functools import cache
import json
from typing import Any
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import dataclass_from_dict
from matter_server.common.models import EventType, MatterNodeData
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture

FIXTURES = [
    "air_quality_sensor",
    "aqara_door_window_p2",
    "aqara_motion_p2",
    "aqara_presence_fp300",
    "aqara_sensor_w100",
    "aqara_thermostat_w500",
    "aqara_u200",
    "color_temperature_light",
    "eberle_ute3000",
    "ecovacs_deebot",
    "eufy_vacuum_omni_e28",
    "eve_contact_sensor",
    "eve_energy_20ecn4101",
    "eve_energy_plug",
    "eve_energy_plug_patched",
    "eve_shutter",
    "eve_thermo_v4",
    "eve_thermo_v5",
    "eve_weather_sensor",
    "extended_color_light",
    "haojai_switch",
    "heiman_co_sensor",
    "heiman_motion_sensor_m1",
    "heiman_smoke_detector",
    "ikea_air_quality_monitor",
    "ikea_scroll_wheel",
    "inovelli_vtm30",
    "inovelli_vtm31",
    "longan_link_thermostat",
    "mock_air_purifier",
    "mock_battery_storage",
    "mock_cooktop",
    "mock_dimmable_light",
    "mock_dimmable_plugin_unit",
    "mock_door_lock",
    "mock_door_lock_with_unbolt",
    "mock_extractor_hood",
    "mock_fan",
    "mock_flow_sensor",
    "mock_generic_switch",
    "mock_generic_switch_multi",
    "mock_humidity_sensor",
    "mock_laundry_dryer",
    "mock_leak_sensor",
    "mock_light_sensor",
    "mock_lock",
    "mock_microwave_oven",
    "mock_mounted_dimmable_load_control_fixture",
    "mock_occupancy_sensor",
    "mock_on_off_plugin_unit",
    "mock_onoff_light",
    "mock_onoff_light_alt_name",
    "mock_onoff_light_no_name",
    "mock_oven",
    "mock_pressure_sensor",
    "mock_pump",
    "mock_room_airconditioner",
    "mock_solar_inverter",
    "mock_speaker",
    "mock_switch_unit",
    "mock_temperature_sensor",
    "mock_thermostat",
    "mock_vacuum_cleaner",
    "mock_valve",
    "mock_window_covering_full",
    "mock_window_covering_lift",
    "mock_window_covering_pa_lift",
    "mock_window_covering_pa_tilt",
    "mock_window_covering_tilt",
    "onoff_light_with_levelcontrol_present",
    "resideo_x2s_thermostat",
    "secuyou_smart_lock",
    "silabs_dishwasher",
    "silabs_evse_charging",
    "silabs_laundrywasher",
    "silabs_light_switch",
    "silabs_refrigerator",
    "silabs_water_heater",
    "switchbot_k11_plus",
    "tado_smart_radiator_thermostat_x",
    "yandex_smart_socket",
    "zemismart_mt25b",
]


@cache
def load_node_fixture(fixture: str) -> str:
    """Load a fixture."""
    return load_fixture(f"matter/nodes/{fixture}.json")


def load_and_parse_node_fixture(fixture: str) -> dict[str, Any]:
    """Load and parse a node fixture."""
    return json.loads(load_node_fixture(fixture))


async def _setup_integration_with_nodes(
    hass: HomeAssistant,
    client: MagicMock,
    nodes: list[MatterNode],
) -> MatterNode:
    """Set up Matter integration with nodes."""
    client.get_nodes.return_value = nodes

    def _get_node(node_id: int) -> MatterNode:
        try:
            next(node for node in nodes if node.node_id == node_id)
        except StopIteration as err:
            raise KeyError(f"Node with id {node_id} not found") from err

    client.get_node.side_effect = _get_node
    config_entry = MockConfigEntry(
        domain="matter", data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def setup_integration_with_node_fixture(
    hass: HomeAssistant,
    node_fixture: str,
    client: MagicMock,
    override_attributes: dict[str, Any] | None = None,
) -> MatterNode:
    """Set up Matter integration with single fixture as node."""
    node = create_node_from_fixture(node_fixture, override_attributes)

    await _setup_integration_with_nodes(hass, client, [node])

    return node


async def setup_integration_with_node_fixtures(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Set up Matter integration with all fixtures as nodes."""
    nodes = [
        create_node_from_fixture(node_fixture, override_serial=True)
        for node_fixture in FIXTURES
    ]

    await _setup_integration_with_nodes(hass, client, nodes)


def create_node_from_fixture(
    node_fixture: str,
    override_attributes: dict[str, Any] | None = None,
    *,
    override_serial: bool = False,
) -> MatterNode:
    """Create a node from a fixture."""
    node_data = load_and_parse_node_fixture(node_fixture)
    # Override serial number to ensure uniqueness across fixtures
    if override_serial and "0/40/15" in node_data["attributes"]:
        node_data["attributes"]["0/40/15"] = f"serial_{node_data['node_id']}"
    if override_attributes:
        node_data["attributes"].update(override_attributes)
    return MatterNode(
        dataclass_from_dict(
            MatterNodeData,
            node_data,
        )
    )


def set_node_attribute(
    node: MatterNode,
    endpoint: int,
    cluster_id: int,
    attribute_id: int,
    value: Any,
) -> None:
    """Set a node attribute."""
    attribute_path = f"{endpoint}/{cluster_id}/{attribute_id}"
    node.endpoints[endpoint].set_attribute_value(attribute_path, value)


async def trigger_subscription_callback(
    hass: HomeAssistant,
    client: MagicMock,
    event: EventType = EventType.ATTRIBUTE_UPDATED,
    data: Any = None,
) -> None:
    """Trigger a subscription callback."""
    # trigger callback on all subscribers
    for sub in client.subscribe_events.call_args_list:
        callback = sub.kwargs["callback"]
        event_filter = sub.kwargs.get("event_filter")
        if event_filter in (None, event):
            callback(event, data)
    await hass.async_block_till_done()


@cache
def _get_fixture_name(node_id: int) -> dict[int, str]:
    """Get the fixture name for a given node ID."""
    for fixture_name in FIXTURES:
        fixture_data = load_and_parse_node_fixture(fixture_name)
        if fixture_data["node_id"] == node_id:
            return fixture_name

    raise KeyError(f"Fixture for node id {node_id} not found")


def snapshot_matter_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot Matter entities."""
    entities = hass.states.async_all(platform)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        node_id = int(entity_entry.unique_id.split("-")[1], 16)
        fixture_name = _get_fixture_name(node_id)
        assert entity_entry == snapshot(
            name=f"{fixture_name}][{entity_entry.entity_id}-entry"
        )
        assert entity_state == snapshot(
            name=f"{fixture_name}][{entity_entry.entity_id}-state"
        )
