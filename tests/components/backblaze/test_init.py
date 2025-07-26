"""Test the Backblaze storage integration."""

from unittest.mock import patch

from b2sdk.v2 import exception
import pytest

from homeassistant.components.backblaze.const import CONF_APPLICATION_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry with invalid auth."""
    mock_config = MockConfigEntry(
        entry_id=mock_config_entry.entry_id,
        title=mock_config_entry.title,
        domain=mock_config_entry.domain,
        data={
            **mock_config_entry.data,
            CONF_APPLICATION_KEY: "invalid_key_id",
        },
    )

    await setup_integration(hass, mock_config)

    assert mock_config.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (exception.Unauthorized("msg", "code"), ConfigEntryState.SETUP_ERROR),
        (exception.RestrictedBucket("testBucket"), ConfigEntryState.SETUP_ERROR),
        (exception.NonExistentBucket(), ConfigEntryState.SETUP_ERROR),
        (exception.ConnectionReset(), ConfigEntryState.SETUP_RETRY),
        (exception.MissingAccountData("key"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_restricted_bucket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup entry with restricted bucket."""

    with patch(
        "b2sdk.v2.RawSimulator.get_bucket_by_name",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
