"""Tests for the devolo Home Control cover platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockCover


async def test_cover(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a cover device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockCover()
    test_gateway.devices["Test"].multi_level_switch_property["devolo.Blinds"].value = 20
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state == snapshot
    assert entity_registry.async_get(f"{DOMAIN}.test") == snapshot

    # Emulate websocket message: position changed
    test_gateway.publisher.dispatch("Test", ("devolo.Blinds", 0.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{DOMAIN}.test")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0.0

    # Test setting position
    with patch(
        "devolo_home_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set_value:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: f"{DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(100)

        set_value.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: f"{DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(0)

        set_value.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: f"{DOMAIN}.test", ATTR_POSITION: 50},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(50)

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == STATE_UNAVAILABLE


async def test_remove_from_hass(hass: HomeAssistant) -> None:
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockCover()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert test_gateway.publisher.unregister.call_count == 1
