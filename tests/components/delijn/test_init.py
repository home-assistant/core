"""Test the De Lijn integration setup."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pydelijn import DeLijnAuthError, DeLijnConnectionError

from homeassistant.components.delijn.const import (
    CONF_NUMBER_OF_DEPARTURES,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import STOP_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test loading and unloading the config entry."""
    mock_config_entry_with_subentry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_with_subentry.state is ConfigEntryState.LOADED
    assert len(mock_config_entry_with_subentry.runtime_data) == 1

    assert await hass.config_entries.async_unload(
        mock_config_entry_with_subentry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_config_entry_with_subentry.state is ConfigEntryState.NOT_LOADED


async def test_load_config_entry_without_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test loading a main entry that has no stop subentries yet."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {}


async def test_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test setup retry when the first refresh fails."""
    mock_delijn_client.get_passages.side_effect = DeLijnConnectionError
    mock_config_entry_with_subentry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentry.state is ConfigEntryState.SETUP_RETRY


async def test_first_refresh_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test a reauth flow is started when the first refresh fails to authenticate."""
    mock_delijn_client.get_passages.side_effect = DeLijnAuthError
    mock_config_entry_with_subentry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry_with_subentry.entry_id


async def test_update_auth_failure_starts_reauth(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a reauth flow is started when a later update fails to authenticate."""
    assert load_integration.state is ConfigEntryState.LOADED

    mock_delijn_client.get_passages.side_effect = DeLijnAuthError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == load_integration.entry_id


async def test_reconfigure_number_of_departures_reloads(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test changing a stop's options reloads the entry and takes effect."""
    subentry_id = next(iter(load_integration.subentries))

    result = await hass.config_entries.subentries.async_init(
        (load_integration.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NUMBER_OF_DEPARTURES: 3}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert load_integration.subentries[subentry_id].data[CONF_NUMBER_OF_DEPARTURES] == 3
    mock_delijn_client.get_passages.assert_called_with(STOP_NUMBER, 3)
