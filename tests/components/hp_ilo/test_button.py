"""Tests for the HP iLO button platform."""

from unittest.mock import MagicMock, patch

import hpilo
import pytest

from homeassistant.components import button
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    "button": {
        "platform": "hp_ilo",
        "host": "192.168.1.1",
        "username": "admin",
        "password": "secret",
        "port": 443,
        "name": "Test Server",
    }
}


@pytest.fixture
def mock_ilo() -> MagicMock:
    """Return a mock hpilo.Ilo instance."""
    mock = MagicMock()
    with patch("homeassistant.components.hp_ilo.button.hpilo.Ilo", return_value=mock):
        yield mock


async def test_setup_creates_all_buttons(
    hass: HomeAssistant, mock_ilo: MagicMock
) -> None:
    """All five power buttons are created with correct names."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    expected = [
        "button.test_server_power_on",
        "button.test_server_power_off",
        "button.test_server_press_power_button",
        "button.test_server_cold_boot",
        "button.test_server_warm_boot",
    ]
    for entity_id in expected:
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"


async def test_press_power_on(hass: HomeAssistant, mock_ilo: MagicMock) -> None:
    """Pressing Power On calls set_host_power(host_power=True)."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_power_on"},
        blocking=True,
    )

    mock_ilo.set_host_power.assert_called_once_with(host_power=True)


async def test_press_power_off(hass: HomeAssistant, mock_ilo: MagicMock) -> None:
    """Pressing Power Off calls set_host_power(host_power=False)."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_power_off"},
        blocking=True,
    )

    mock_ilo.set_host_power.assert_called_once_with(host_power=False)


async def test_press_power_button(hass: HomeAssistant, mock_ilo: MagicMock) -> None:
    """Pressing Press Power Button calls press_pwr_btn()."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_press_power_button"},
        blocking=True,
    )

    mock_ilo.press_pwr_btn.assert_called_once_with()


async def test_press_cold_boot(hass: HomeAssistant, mock_ilo: MagicMock) -> None:
    """Pressing Cold Boot calls cold_boot_server()."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_cold_boot"},
        blocking=True,
    )

    mock_ilo.cold_boot_server.assert_called_once_with()


async def test_press_warm_boot(hass: HomeAssistant, mock_ilo: MagicMock) -> None:
    """Pressing Warm Boot calls warm_boot_server()."""
    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_warm_boot"},
        blocking=True,
    )

    mock_ilo.warm_boot_server.assert_called_once_with()


async def test_press_logs_error_on_ilo_failure(
    hass: HomeAssistant, mock_ilo: MagicMock
) -> None:
    """A failed iLO call is logged and does not raise."""
    mock_ilo.set_host_power.side_effect = hpilo.IloError("connection refused")

    assert await async_setup_component(hass, "button", VALID_CONFIG)
    await hass.async_block_till_done()

    # Should not raise despite the iLO error
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_server_power_on"},
        blocking=True,
    )

    mock_ilo.set_host_power.assert_called_once_with(host_power=True)
