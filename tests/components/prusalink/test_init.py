"""Test setting up and unloading PrusaLink."""
from datetime import timedelta
from unittest.mock import patch

from pyprusalink.types import InvalidAuth, PrusaLinkError
import pytest

from homeassistant.components.prusalink import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_unloading(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_api,
) -> None:
    """Test unloading prusalink."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert hass.states.async_entity_ids_count() > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    for state in hass.states.async_all():
        assert state.state == "unavailable"


@pytest.mark.parametrize("exception", [InvalidAuth, PrusaLinkError])
async def test_failed_update(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_api, exception
) -> None:
    """Test failed update marks prusalink unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.prusalink.PrusaLink.get_version",
        side_effect=exception,
    ), patch(
        "homeassistant.components.prusalink.PrusaLink.get_status",
        side_effect=exception,
    ), patch(
        "homeassistant.components.prusalink.PrusaLink.get_legacy_printer",
        side_effect=exception,
    ), patch(
        "homeassistant.components.prusalink.PrusaLink.get_job",
        side_effect=exception,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30), fire_all=True)
        await hass.async_block_till_done()

    for state in hass.states.async_all():
        assert state.state == "unavailable"


async def test_migration_1_2(hass: HomeAssistant, mock_api) -> None:
    """Test migrating from version 1 to 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://prusaxl.local",
            CONF_API_KEY: "api-key",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)

    # Ensure that we have username, password after migration
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        CONF_HOST: "http://prusaxl.local",
        CONF_USERNAME: "maker",
        CONF_PASSWORD: "api-key",
    }


async def test_outdated_firmware_migration_1_2(hass: HomeAssistant, mock_api) -> None:
    """Test migrating from version 1 to 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://prusaxl.local",
            CONF_API_KEY: "api-key",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "pyprusalink.PrusaLink.get_info",
        side_effect=InvalidAuth,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.SETUP_ERROR
