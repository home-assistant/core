"""Test KNX scene."""
from unittest.mock import patch

from xknx.core import XknxConnectionState, XknxConnectionType
from xknx.telegram import IndividualAddress

from homeassistant.components.knx.sensor import SCAN_INTERVAL
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed


async def test_diagnostic_entities(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test diagnostic entities."""
    await knx.setup_integration({})

    for entity_id in [
        "sensor.knx_interface_individual_address",
        "sensor.knx_interface_connection_established",
        "sensor.knx_interface_connection_type",
        "sensor.knx_interface_incoming_telegrams",
        "sensor.knx_interface_incoming_telegram_errors",
        "sensor.knx_interface_outgoing_telegrams",
        "sensor.knx_interface_outgoing_telegram_errors",
        "sensor.knx_interface_telegrams",
    ]:
        entity = entity_registry.async_get(entity_id)
        assert entity.entity_category is EntityCategory.DIAGNOSTIC

    for entity_id in [
        "sensor.knx_interface_incoming_telegrams",
        "sensor.knx_interface_outgoing_telegrams",
    ]:
        entity = entity_registry.async_get(entity_id)
        assert entity.disabled is True

    knx.xknx.connection_manager.cemi_count_incoming = 20
    knx.xknx.connection_manager.cemi_count_incoming_error = 1
    knx.xknx.connection_manager.cemi_count_outgoing = 10
    knx.xknx.connection_manager.cemi_count_outgoing_error = 2

    events = async_capture_events(hass, "state_changed")
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert len(events) == 3  # 5 polled sensors - 2 disabled
    events.clear()

    for entity_id, test_state in [
        ("sensor.knx_interface_individual_address", "0.0.0"),
        ("sensor.knx_interface_connection_type", "Tunnel TCP"),
        # skipping connected_since timestamp
        ("sensor.knx_interface_incoming_telegram_errors", "1"),
        ("sensor.knx_interface_outgoing_telegram_errors", "2"),
        ("sensor.knx_interface_telegrams", "31"),
    ]:
        assert hass.states.get(entity_id).state == test_state

    await knx.xknx.connection_manager.connection_state_changed(
        state=XknxConnectionState.DISCONNECTED
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(events) == 4  # 3 not always_available + 3 force_update - 2 disabled
    events.clear()

    knx.xknx.current_address = IndividualAddress("1.1.1")
    await knx.xknx.connection_manager.connection_state_changed(
        state=XknxConnectionState.CONNECTED,
        connection_type=XknxConnectionType.TUNNEL_UDP,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(events) == 6  # all diagnostic sensors - counters are reset on connect

    for entity_id, test_state in [
        ("sensor.knx_interface_individual_address", "1.1.1"),
        ("sensor.knx_interface_connection_type", "Tunnel UDP"),
        # skipping connected_since timestamp
        ("sensor.knx_interface_incoming_telegram_errors", "0"),
        ("sensor.knx_interface_outgoing_telegram_errors", "0"),
        ("sensor.knx_interface_telegrams", "0"),
    ]:
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
        await hass.async_block_till_done()
        unregister_mock.assert_called_once()
