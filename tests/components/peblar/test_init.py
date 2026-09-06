"""Integration tests for the Peblar integration."""

from unittest.mock import MagicMock

from peblar import PeblarAuthenticationError, PeblarConnectionError, PeblarError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
) -> None:
    """Test the Peblar configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_peblar.login.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "translation_key", "reason"),
    [
        (
            PeblarConnectionError("Could not connect"),
            "communication_error",
            "An error occurred while communicating with the Peblar EV charger: "
            "Could not connect",
        ),
        (
            PeblarError("Unknown error"),
            "unknown_error",
            "An unknown error occurred while communicating with the Peblar EV "
            "charger: Unknown error",
        ),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    exception: Exception,
    translation_key: str,
    reason: str,
) -> None:
    """Test the Peblar configuration entry not ready.

    The reason reaches the user, so it comes from strings.json rather than
    from a sentence typed into the raise.
    """
    mock_peblar.login.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_peblar.login.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.reason == reason


async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
) -> None:
    """Test authentication error, aborts setup."""
    mock_config_entry.add_to_hass(hass)

    mock_peblar.login.side_effect = PeblarAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "authentication_error"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.usefixtures("init_integration")
async def test_peblar_device_entry(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test authentication error, aborts setup."""
    assert (
        device_entry := device_registry.async_get_device_by_identifier(
            (DOMAIN, "23-45-A4O-MOF"), mock_config_entry.entry_id
        )
    )
    assert device_entry == snapshot
