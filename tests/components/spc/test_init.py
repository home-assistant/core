"""Tests for Vanderbilt SPC component."""
from unittest.mock import Mock, PropertyMock, patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.spc.const import DOMAIN
from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED, Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import mock_coro


async def test_valid_device_config(hass: HomeAssistant, monkeypatch) -> None:
    """Test valid device config."""
    config = {"spc": {"api_url": "http://localhost/", "ws_url": "ws://localhost/"}}

    with patch("pyspcwebgw.SpcWebGateway.info", new_callable=PropertyMock) as mock_info:
        mock_info.return_value = {"sn": "111111", "type": "example"}
        with patch(
            "pyspcwebgw.SpcWebGateway.async_load_parameters",
            return_value=mock_coro(True),
        ):
            assert await async_setup_component(hass, "spc", config) is True


async def test_invalid_device_config(hass: HomeAssistant, monkeypatch) -> None:
    """Test valid device config."""
    config = {"spc": {"api_url": "http://localhost/"}}

    with patch(
        "pyspcwebgw.SpcWebGateway.async_load_parameters",
        return_value=mock_coro(True),
    ):
        assert await async_setup_component(hass, "spc", config) is False


async def test_update_alarm_device(hass: HomeAssistant) -> None:
    """Test that alarm panel state changes on incoming websocket data."""
    import pyspcwebgw
    from pyspcwebgw.const import AreaMode

    area_mock = Mock(
        spec=pyspcwebgw.area.Area,
        id="1",
        mode=AreaMode.FULL_SET,
        last_changed_by="Sven",
    )
    area_mock.name = "House"
    area_mock.verified_alarm = False

    with patch(
        "pyspcwebgw.SpcWebGateway.areas", new_callable=PropertyMock
    ) as mock_areas:
        mock_areas.return_value = {"1": area_mock}
        with patch(
            "pyspcwebgw.SpcWebGateway.async_load_parameters",
            return_value=mock_coro(True),
        ):
            await setup_platform(hass, Platform.ALARM_CONTROL_PANEL)

    entity_id = "alarm_control_panel.house"

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY
    assert hass.states.get(entity_id).attributes["changed_by"] == "Sven"

    area_mock.mode = AreaMode.UNSET
    area_mock.last_changed_by = "Anna"
    await hass.data[DOMAIN]["281c613684f295115f3948e7b9b1be94"]._async_callback(
        area_mock
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED
    assert hass.states.get(entity_id).attributes["changed_by"] == "Anna"
