"""Test the Bosch SHC setup/unload."""

from unittest.mock import MagicMock

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Test a successful setup and unload of the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_dependencies.async_init.assert_awaited_once()
    mock_setup_dependencies.start_polling.assert_awaited_once()

    # The controller itself is registered as a device.
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-mac")}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "10.0.0"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_setup_dependencies.stop_polling.assert_awaited_once()


async def test_setup_expired_certificate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """An expired client certificate triggers reauth (ConfigEntryAuthFailed)."""
    from unittest.mock import patch

    cert_info = MagicMock()
    cert_info.days_remaining = -1
    cert_info.not_after = MagicMock()

    with (
        patch(
            "homeassistant.components.bosch_shc.parse_certificate",
            return_value=cert_info,
        ),
        patch(
            "homeassistant.components.bosch_shc.build_ssl_context",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.bosch_shc.SHCSessionAsync",
            return_value=mock_session,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
