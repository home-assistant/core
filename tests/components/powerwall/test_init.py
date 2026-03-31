"""Tests for Powerwall integration setup."""

from unittest.mock import MagicMock, patch

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .mocks import create_mock_powerwall_pw2, create_mock_powerwall_pw3

from tests.common import MockConfigEntry


async def test_setup_entry_pw3(hass: HomeAssistant) -> None:
    """Test successful setup with Powerwall 3."""
    mock_pw = create_mock_powerwall_pw3()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert config_entry.runtime_data["base_info"].is_powerwall3 is True
    assert config_entry.runtime_data["base_info"].device_type == "Powerwall 3"


async def test_setup_entry_pw2(hass: HomeAssistant) -> None:
    """Test successful setup with Powerwall 2."""
    mock_pw = create_mock_powerwall_pw2()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert config_entry.runtime_data["base_info"].is_powerwall3 is False
    assert config_entry.runtime_data["base_info"].device_type == "Powerwall 2"
    assert config_entry.runtime_data["base_info"].site_name == "My Home"


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test setup with connection error."""
    mock_pw = MagicMock()
    mock_pw.level.return_value = None

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_exception(hass: HomeAssistant) -> None:
    """Test setup with exception."""
    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        side_effect=Exception("Connection failed"),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_IP_ADDRESS: "192.168.1.100",
                CONF_PASSWORD: "test123",
            },
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the config entry."""
    mock_pw = create_mock_powerwall_pw3()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
