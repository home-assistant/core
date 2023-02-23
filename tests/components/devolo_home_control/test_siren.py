"""Tests for the devolo Home Control binary sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.siren import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockSiren


@pytest.mark.usefixtures("mock_zeroconf")
async def test_siren(hass: HomeAssistant) -> None:
    """Test setup and state change of a siren device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSiren()
    test_gateway.devices["Test"].status = 0
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test"

    # Emulate websocket message: sensor turned on
    test_gateway.publisher.dispatch("Test", ("devolo.SirenMultiLevelSwitch:Test", 1))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == STATE_ON

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_zeroconf")
async def test_siren_switching(hass: HomeAssistant) -> None:
    """Test setup and state change via switching of a siren device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSiren()
    test_gateway.devices["Test"].status = 0
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None
    assert state.state == STATE_OFF

    with patch(
        "devolo_home_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set:
        await hass.services.async_call(
            "siren",
            "turn_on",
            {"entity_id": f"{DOMAIN}.test"},
            blocking=True,
        )
        # The real device state is changed by a websocket message
        test_gateway.publisher.dispatch(
            "Test", ("devolo.SirenMultiLevelSwitch:Test", 1)
        )
        await hass.async_block_till_done()
        set.assert_called_once_with(1)

    with patch(
        "devolo_home_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set:
        await hass.services.async_call(
            "siren",
            "turn_off",
            {"entity_id": f"{DOMAIN}.test"},
            blocking=True,
        )
        # The real device state is changed by a websocket message
        test_gateway.publisher.dispatch(
            "Test", ("devolo.SirenMultiLevelSwitch:Test", 0)
        )
        await hass.async_block_till_done()
        assert hass.states.get(f"{DOMAIN}.test").state == STATE_OFF
        set.assert_called_once_with(0)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_siren_change_default_tone(hass: HomeAssistant) -> None:
    """Test changing the default tone on message."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSiren()
    test_gateway.devices["Test"].status = 0
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None

    with patch(
        "devolo_home_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set:
        test_gateway.publisher.dispatch("Test", ("mss:Test", 2))
        await hass.services.async_call(
            "siren",
            "turn_on",
            {"entity_id": f"{DOMAIN}.test"},
            blocking=True,
        )
        set.assert_called_once_with(2)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_from_hass(hass: HomeAssistant) -> None:
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSiren()
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
    test_gateway.publisher.unregister.assert_called_once()
