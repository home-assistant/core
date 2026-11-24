"""Tests for the Elvia integration setup."""

from datetime import timedelta
from unittest.mock import patch

from elvia import error as ElviaError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.elvia.const import CONF_METERING_POINT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.mark.usefixtures("recorder_mock")
async def test_setup_import_failed(hass: HomeAssistant) -> None:
    """Test setup fails when the initial import of meter values fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elvia.importer.ElviaImporter.import_meter_values",
        side_effect=ElviaError.ElviaException("Boom"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to import meter values from Elvia"


@pytest.mark.usefixtures("recorder_mock")
async def test_setup_auth_failed(hass: HomeAssistant) -> None:
    """Test setup starts a reauth flow on an authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        side_effect=ElviaError.AuthError("Boom", 401, {}, ""),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.usefixtures("recorder_mock")
async def test_scheduled_import_auth_failed(hass: HomeAssistant) -> None:
    """Test a scheduled import starts a reauth flow on an authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elvia.importer.ElviaImporter.import_meter_values",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        side_effect=ElviaError.AuthError("Boom", 401, {}, ""),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=61))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.usefixtures("recorder_mock")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the entry unloads and stops the scheduled import."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elvia.importer.ElviaImporter.import_meter_values",
    ) as mock_import:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=61))
        await hass.async_block_till_done()

    assert mock_import.call_count == 1
