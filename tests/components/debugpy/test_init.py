"""Tests for the Remote Python Debugger integration."""
import pytest

from homeassistant.components.debugpy import (
    CONF_HOST,
    CONF_PORT,
    CONF_START,
    CONF_WAIT,
    DOMAIN,
    SERVICE_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


@pytest.fixture
def mock_debugpy():
    """Mock path lib."""
    with patch("homeassistant.components.debugpy.debugpy") as mocked_debugpy:
        yield mocked_debugpy


async def test_default(hass: HomeAssistant, mock_debugpy) -> None:
    """Test if the default settings work."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_debugpy.listen.assert_called_once_with(("0.0.0.0", 5678))
    mock_debugpy.wait_for_client.assert_not_called()


async def test_wait_on_startup(hass: HomeAssistant, mock_debugpy) -> None:
    """Test if the default settings work."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_WAIT: True}})

    mock_debugpy.listen.assert_called_once_with(("0.0.0.0", 5678))
    mock_debugpy.wait_for_client.assert_called_once()


async def test_on_demand(hass: HomeAssistant, mock_debugpy) -> None:
    """Test if the default settings work."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_START: False, CONF_HOST: "127.0.0.1", CONF_PORT: 80}},
    )

    mock_debugpy.listen.assert_not_called()
    mock_debugpy.wait_for_client.assert_not_called()

    await hass.services.async_call(
        DOMAIN, SERVICE_START, blocking=True,
    )

    mock_debugpy.listen.assert_called_once_with(("127.0.0.1", 80))
    mock_debugpy.wait_for_client.assert_not_called()
