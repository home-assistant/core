"""Test the Teltonika integration."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError, ContentTypeError
import pytest
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_teltasync_init: MagicMock,
    mock_modems: MagicMock,
) -> MockConfigEntry:
    """Set up the Teltonika integration for testing."""
    device_data = await async_load_json_object_fixture(hass, "device_data.json", DOMAIN)  # type: ignore[misc]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test_password",
        },
        unique_id=device_data["system_info"]["mnf_info"]["serial"],
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync_init: MagicMock,
) -> None:
    """Test connection error during setup."""
    mock_teltasync_init.return_value.get_device_info.side_effect = (
        TeltonikaConnectionError("Connection failed")
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failure_recovery(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modems: MagicMock,
) -> None:
    """Test coordinator recovery after update failure."""
    coordinator = init_integration.runtime_data.coordinator

    mock_modems_instance = mock_modems.return_value
    mock_modems_instance.get_status.side_effect = TeltonikaConnectionError(
        "Connection lost"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Simulate recovery
    mock_modems_instance.get_status.side_effect = None

    data = await coordinator._async_update_data()
    assert data
    coordinator.async_set_updated_data(data)


async def test_device_registry_creation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry creation."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert device is not None
    assert device.name == "Test Device"
    assert device.manufacturer == "Teltonika"


async def test_device_removal_on_config_entry_removal(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device removal when config entry is removed."""
    # Verify device exists
    device = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert device is not None

    # Remove config entry
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    # Device should be removed when config entry is removed (this is the correct HA behavior)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert device is None


async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync_init: MagicMock,
) -> None:
    """Test various setup exceptions."""
    mock_teltasync_init.return_value.get_device_info.side_effect = (
        TeltonikaConnectionError("Connection failed")
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_data_structure(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator data structure."""
    coordinator = init_integration.runtime_data.coordinator

    # Verify coordinator exposes the modem map
    assert coordinator.data is not None
    assert isinstance(coordinator.data, dict)
    assert "2-1" in coordinator.data


@pytest.mark.parametrize(
    ("exception", "error_status"),
    [
        (
            ContentTypeError(
                request_info=MagicMock(),
                history=(),
                status=403,
                message="Attempt to decode JSON with unexpected mimetype: text/html",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=401,
                message="Unauthorized",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=403,
                message="Forbidden",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            TeltonikaAuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
    ids=[
        "content_type_403",
        "response_401",
        "response_403",
        "auth_error",
    ],
)
async def test_setup_auth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync_init: MagicMock,
    exception: Exception,
    error_status: ConfigEntryState,
) -> None:
    """Test various authentication errors trigger reauth flow."""
    mock_teltasync_init.return_value.get_device_info.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is error_status
