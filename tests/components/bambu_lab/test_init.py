"""Tests for the setup of the Bambu Lab integration."""

from unittest.mock import MagicMock

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabConnectionError,
    BambuLabSerialMismatchError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bambu_lab.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import ACCESS_CODE, HOST, SERIAL_NUMBER


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_bambu_lab_client_class: MagicMock,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_bambu_lab_client_class.assert_called_once_with(
        HOST, SERIAL_NUMBER, ACCESS_CODE
    )
    mock_bambu_lab_client.connect.assert_awaited_once()
    mock_bambu_lab_client.disconnect.assert_not_called()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_bambu_lab_client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        pytest.param(
            BambuLabAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            id="invalid_auth",
        ),
        pytest.param(
            BambuLabConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
        pytest.param(
            BambuLabSerialMismatchError,
            ConfigEntryState.SETUP_RETRY,
            id="serial_number_mismatch",
        ),
        pytest.param(
            BambuLabCertificateError,
            ConfigEntryState.SETUP_RETRY,
            id="untrusted_certificate",
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test the config entry is not loaded when the printer cannot be reached."""
    mock_bambu_lab_client.connect.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_disconnect_on_stop(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration disconnects when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_bambu_lab_client.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device of the printer."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot
