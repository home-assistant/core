"""Test KNX interface device."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from xknx.core import XknxConnectionState, XknxConnectionType
from xknx.telegram import IndividualAddress

from homeassistant.components.knx.sensor import SCAN_INTERVAL
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_diagnostic_entities(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostic entities."""
    await knx.setup_integration({})

    for entity_id in (
        "sensor.knx_interface_individual_address",
        "sensor.knx_interface_connection_established",
        "sensor.knx_interface_connection_type",
        "sensor.knx_interface_incoming_telegrams",
        "sensor.knx_interface_incoming_telegram_errors",
        "sensor.knx_interface_outgoing_telegrams",
        "sensor.knx_interface_outgoing_telegram_errors",
        "sensor.knx_interface_telegrams",
    ):
        entity = entity_registry.async_get(entity_id)
        assert entity.entity_category is EntityCategory.DIAGNOSTIC

    for entity_id in (
        "sensor.knx_interface_incoming_telegrams",
        "sensor.knx_interface_outgoing_telegrams",
    ):
        entity = entity_registry.async_get(entity_id)
        assert entity.disabled is True

    knx.xknx.connection_manager.cemi_count_incoming = 20
    knx.xknx.connection_manager.cemi_count_incoming_error = 1
    knx.xknx.connection_manager.cemi_count_outgoing = 10
    knx.xknx.connection_manager.cemi_count_outgoing_error = 2

    events = async_capture_events(hass, "state_changed")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(events) == 3  # 5 polled sensors - 2 disabled
    events.clear()

    for entity_id, test_state in (
        ("sensor.knx_interface_individual_address", "0.0.0"),
        ("sensor.knx_interface_connection_type", "Tunnel TCP"),
        # skipping connected_since timestamp
        ("sensor.knx_interface_incoming_telegram_errors", "1"),
        ("sensor.knx_interface_outgoing_telegram_errors", "2"),
        ("sensor.knx_interface_telegrams", "31"),
    ):
        assert hass.states.get(entity_id).state == test_state

    knx.xknx.connection_manager.connection_state_changed(
        state=XknxConnectionState.DISCONNECTED
    )
    await hass.async_block_till_done()
    assert len(events) == 4  # 3 not always_available + 3 force_update - 2 disabled
    events.clear()

    knx.xknx.current_address = IndividualAddress("1.1.1")
    knx.xknx.connection_manager.connection_state_changed(
        state=XknxConnectionState.CONNECTED,
        connection_type=XknxConnectionType.TUNNEL_UDP,
    )
    await hass.async_block_till_done()
    assert len(events) == 6  # all diagnostic sensors - counters are reset on connect

    for entity_id, test_state in (
        ("sensor.knx_interface_individual_address", "1.1.1"),
        ("sensor.knx_interface_connection_type", "Tunnel UDP"),
        # skipping connected_since timestamp
        ("sensor.knx_interface_incoming_telegram_errors", "0"),
        ("sensor.knx_interface_outgoing_telegram_errors", "0"),
        ("sensor.knx_interface_telegrams", "0"),
    ):
        assert hass.states.get(entity_id).state == test_state


async def test_removed_entity(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test unregister callback when entity is removed."""
    with patch(
        "xknx.core.connection_manager.ConnectionManager.unregister_connection_state_changed_cb"
    ) as unregister_mock:
        await knx.setup_integration({})

        entity_registry.async_update_entity(
            "sensor.knx_interface_connection_established",
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        unregister_mock.assert_called_once()


async def test_remove_interface_device(
    hass: HomeAssistant,
    knx: KNXTestKit,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test device removal."""
    assert await async_setup_component(hass, "config", {})
    await knx.setup_integration({})
    client = await hass_ws_client(hass)
    knx_devices = device_registry.devices.get_devices_for_config_entry_id(
        knx.mock_config_entry.entry_id
    )
    assert len(knx_devices) == 1
    assert knx_devices[0].name == "KNX Interface"
    device_id = knx_devices[0].id
    # interface device can't be removed
    res = await client.remove_device(device_id, knx.mock_config_entry.entry_id)
    assert not res["success"]
    assert (
        res["error"]["message"]
        == "Failed to remove device entry, rejected by integration"
    )
