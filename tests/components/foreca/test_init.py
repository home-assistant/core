"""Test the Foreca integration setup."""

from unittest.mock import AsyncMock, MagicMock

from pyforeca import ForecaAuthError, ForecaConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.foreca.const import DOMAIN, SUBENTRY_TYPE_LOCATION
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import init_integration


@pytest.mark.usefixtures("mock_foreca_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test the entry is retried when the API is unreachable."""
    mock_foreca_client.current.side_effect = ForecaConnectionError
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_on_rejected_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a rejected API key fails setup instead of retrying."""
    mock_foreca_client.current.side_effect = ForecaAuthError
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_documented_request_budget(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test one update costs the three requests the documentation promises.

    The docs page quotes this number against the Freemium daily limit, so a new
    call added to the coordinator has to be a deliberate change here too.
    """
    await init_integration(hass, mock_config_entry)

    awaited = {
        name: attr.await_count
        for name in dir(mock_foreca_client)
        if not name.startswith("_")
        and isinstance(attr := getattr(mock_foreca_client, name), AsyncMock)
        and attr.await_count
    }
    assert awaited == {"current": 1, "forecast_daily": 1, "forecast_hourly": 1}
    assert sum(awaited.values()) == 3


@pytest.mark.usefixtures("mock_foreca_client")
async def test_added_location_gets_an_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a location added after setup gets its own weather entity."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_all("weather")) == 1

    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data={CONF_LATITUDE: 48.86, CONF_LONGITUDE: 2.35},
            subentry_type=SUBENTRY_TYPE_LOCATION,
            title="Paris",
            unique_id="48.86-2.35",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all("weather")) == 2


@pytest.mark.usefixtures("mock_foreca_client")
async def test_removed_location_loses_its_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a location removes its device and weather entity."""
    await init_integration(hass, mock_config_entry)
    subentry_id = next(iter(mock_config_entry.subentries))
    identifier = (DOMAIN, subentry_id)
    entry_id = mock_config_entry.entry_id
    assert device_registry.async_get_device_by_identifier(identifier, entry_id)

    hass.config_entries.async_remove_subentry(mock_config_entry, subentry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(identifier, entry_id) is None
    assert hass.states.async_all("weather") == []
