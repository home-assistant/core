"""Tests for the blanco integration setup."""

from unittest.mock import MagicMock

from blanco_smart_home_api_client import (
    BlancoApiError,
    BlancoConnectionError,
    HttpStatus,
)
import pytest

from homeassistant.components.blanco.const import CONF_DEV_TYPE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import TEST_DEV_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_blanco_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "errors",
    [
        pytest.param((HttpStatus.INTERNAL_SERVER_ERROR, {}), id="http_error"),
        pytest.param(BlancoConnectionError("timeout"), id="connection_error"),
    ],
)
async def test_setup_retry_when_errors_endpoint_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    errors: tuple[int, dict] | Exception,
) -> None:
    """Test setup is retried when the errors endpoint returns no fresh data."""
    mock_blanco_client.get_device_errors.side_effect = [errors]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "system",
    [
        pytest.param((HttpStatus.INTERNAL_SERVER_ERROR, {}), id="http_error"),
        pytest.param(BlancoConnectionError("timeout"), id="connection_error"),
    ],
)
async def test_setup_succeeds_when_system_endpoint_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    system: tuple[int, dict] | Exception,
) -> None:
    """Test setup succeeds with a default device name when only system data fails."""
    mock_blanco_client.get_device_system.side_effect = [system]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEV_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "BLANCO"


@pytest.mark.parametrize("failing_endpoint", ["get_device_system", "get_device_errors"])
async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    failing_endpoint: str,
) -> None:
    """Test setup fails with an auth error when the API rejects the token."""
    getattr(mock_blanco_client, failing_endpoint).side_effect = BlancoApiError(
        "token rejected"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(None, id="success"),
        pytest.param(BlancoConnectionError("timeout"), id="connection_error"),
    ],
)
async def test_remove_entry_deregisters_app(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    side_effect: Exception | None,
) -> None:
    """Test removing the entry deregisters the app and tolerates network errors."""
    mock_blanco_client.deregister_app.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_blanco_client.deregister_app.assert_awaited_once()
    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id) is None


@pytest.mark.usefixtures("mock_blanco_client")
async def test_unknown_device_type_has_no_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device type unknown to the library leaves the device model empty."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_DEV_TYPE: 999}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEV_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model is None
