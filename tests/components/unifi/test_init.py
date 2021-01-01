"""Test UniFi setup process."""
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components import unifi
from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.setup import async_setup_component

from .test_controller import setup_unifi_integration

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, UNIFI_DOMAIN, {}) is True
    assert UNIFI_DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN]


async def test_controller_fail_setup(hass):
    """Test that a failed setup still stores controller."""
    with patch("homeassistant.components.unifi.UniFiController") as mock_controller:
        mock_controller.return_value.async_setup = AsyncMock(return_value=False)
        await setup_unifi_integration(hass)

    assert hass.data[UNIFI_DOMAIN] == {}


async def test_controller_no_mac(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data={
            "controller": {
                "host": "0.0.0.0",
                "username": "user",
                "password": "pass",
                "port": 80,
                "site": "default",
                "verify_ssl": True,
            },
            "poe_control": True,
        },
    )
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch(
        "homeassistant.components.unifi.UniFiController"
    ) as mock_controller, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(mock_registry),
    ):
        mock_controller.return_value.async_setup = AsyncMock(return_value=True)
        mock_controller.return_value.mac = None
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.mock_calls) == 2

    assert len(mock_registry.mock_calls) == 0


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    controller = await setup_unifi_integration(hass)
    assert hass.data[UNIFI_DOMAIN]

    assert await unifi.async_unload_entry(hass, controller.config_entry)
    assert not hass.data[UNIFI_DOMAIN]
