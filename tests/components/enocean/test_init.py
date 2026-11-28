"""Test the EnOcean integration."""

from unittest.mock import Mock, patch

from enocean_async import SerialProtocol
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.enocean.const import CONF_PROTOCOL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant


async def test_device_not_connected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a config entry is not ready if the device is not connected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.enocean.Gateway.start",
        side_effect=ConnectionError("Device not found"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_stops_gateway(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_gateway: Mock
) -> None:
    """Test that unloading the config entry stops the gateway."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_gateway.stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("entry_data", "expected_protocol"),
    [
        pytest.param(
            {CONF_DEVICE: "/dev/ttyUSB0"}, SerialProtocol.ESP3, id="no_protocol_stored"
        ),
        pytest.param(
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_PROTOCOL: "esp3"},
            SerialProtocol.ESP3,
            id="esp3",
        ),
        pytest.param(
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_PROTOCOL: "esp2"},
            SerialProtocol.ESP2,
            id="esp2",
        ),
    ],
)
async def test_gateway_uses_stored_protocol(
    hass: HomeAssistant,
    mock_gateway_class: Mock,
    entry_data: dict[str, str],
    expected_protocol: SerialProtocol,
) -> None:
    """Test that the gateway is created with the protocol stored in the entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    mock_gateway_class.assert_called_once_with(
        port="/dev/ttyUSB0", protocol=expected_protocol
    )
