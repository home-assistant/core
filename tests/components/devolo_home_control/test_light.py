"""Tests for the devolo Home Control light platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .mocks import BinarySwitchPropertyMock, HomeControlMock, HomeControlMockLight


async def test_light_without_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a light device that does not have an additional binary sensor."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockLight()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state == snapshot
    assert entity_registry.async_get(f"{LIGHT_DOMAIN}.test") == snapshot

    # Emulate websocket message: brightness changed
    test_gateway.publisher.dispatch("Test", ("devolo.Dimmer:Test", 0.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state.state == STATE_OFF
    test_gateway.publisher.dispatch("Test", ("devolo.Dimmer:Test", 100.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    # Test setting brightness
    with patch(
        "devolo_home_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set_value:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(100)

        set_value.reset_mock()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(0)

        set_value.reset_mock()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.test", ATTR_BRIGHTNESS: 50},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(round(50 / 255 * 100))

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{LIGHT_DOMAIN}.test").state == STATE_UNAVAILABLE


async def test_light_with_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a light device that has an additional binary sensor."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockLight()
    test_gateway.devices["Test"].binary_switch_property = {
        "devolo.BinarySwitch:Test": BinarySwitchPropertyMock()
    }
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state == snapshot
    assert entity_registry.async_get(f"{LIGHT_DOMAIN}.test") == snapshot

    # Emulate websocket message: brightness changed
    test_gateway.publisher.dispatch("Test", ("devolo.Dimmer:Test", 0.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state.state == STATE_OFF
    test_gateway.publisher.dispatch("Test", ("devolo.Dimmer:Test", 100.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    # Test setting brightness
    with patch(
        "devolo_home_control_api.properties.binary_switch_property.BinarySwitchProperty.set"
    ) as set_value:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(True)

        set_value.reset_mock()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.test"},
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(False)


async def test_remove_from_hass(hass: HomeAssistant) -> None:
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockLight()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{LIGHT_DOMAIN}.test")
    assert state is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert test_gateway.publisher.unregister.call_count == 1
