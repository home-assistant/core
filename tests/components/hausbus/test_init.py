"""Test the hausbus initialization."""

from unittest.mock import Mock, patch

from pyhausbus.HomeServer import HomeServer

from homeassistant.components.hausbus import async_setup_entry, async_unload_entry
from homeassistant.components.hausbus.const import DOMAIN as HAUSBUS_DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init(hass: HomeAssistant) -> None:
    """Test initialization of the hausbus component."""
    config_entry = MockConfigEntry(
        domain=HAUSBUS_DOMAIN,
        entry_id="1",
    )

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        result = await async_setup_entry(hass, config_entry)

    # Assert the result
    assert result is True
    # Assert device discovery is started
    mock_home_server.searchDevices.assert_called_once()


async def test_unload(hass: HomeAssistant) -> None:
    """Test initialization of the hausbus component."""
    config_entry = MockConfigEntry(
        domain=HAUSBUS_DOMAIN,
        entry_id="1",
    )

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        await async_setup_entry(hass, config_entry)

    gateway = hass.data[HAUSBUS_DOMAIN][config_entry.entry_id]
    result = await async_unload_entry(hass, config_entry)

    # Assert that unload was successful
    assert result is True
    # Assert that the gateway was removed from the Hausbus home server listener
    mock_home_server.removeBusEventListener.assert_called_once_with(gateway)
