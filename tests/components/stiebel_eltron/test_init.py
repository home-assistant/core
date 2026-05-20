"""Tests for the STIEBEL ELTRON integration."""

from unittest.mock import MagicMock

from pystiebeleltron import StiebelEltronModbusError

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the integration."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    assert mock_config_entry.state.name == "LOADED"
    assert mock_config_entry.runtime_data is not None


async def test_async_setup_entry_with_custom_port(
    hass: HomeAssistant,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup with custom port."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 5020},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_get_controller_model.assert_called_once_with("192.168.1.100", 5020)


async def test_async_setup_entry_without_port(
    hass: HomeAssistant,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup without port (should use default)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "192.168.1.100"},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_get_controller_model.assert_called_once_with("192.168.1.100", 502)


async def test_async_setup_entry_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup fails when get_controller_model raises an error."""
    mock_config_entry.add_to_hass(hass)
    mock_get_controller_model.side_effect = StiebelEltronModbusError()

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state.name == "SETUP_ERROR"
