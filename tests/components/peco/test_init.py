"""Test the PECO Outage Counter init file."""
import asyncio
from unittest.mock import patch

from peco import AlertResults, BadJSONError, HttpError, OutageResults
import pytest

from homeassistant.components.peco.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {"county": "TOTAL"}
COUNTY_ENTRY_DATA = {"county": "BUCKS"}
INVALID_COUNTY_DATA = {"county": "INVALID"}


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the unload entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.get_outage_totals",
        return_value=OutageResults(
            customers_out=0,
            percent_customers_out=0,
            outage_count=0,
            customers_served=350394,
        ),
    ), patch(
        "peco.PecoOutageApi.get_map_alerts",
        return_value=AlertResults(
            alert_content="Testing 1234", alert_title="Testing 4321"
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "sensor",
    [
        "bucks_customers_out",
        "bucks_percent_customers_out",
        "bucks_outage_count",
        "bucks_customers_served",
    ],
)
async def test_update_timeout(hass: HomeAssistant, sensor) -> None:
    """Test if it raises an error when there is a timeout."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.get_outage_count",
        side_effect=asyncio.TimeoutError(),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "sensor",
    [
        "total_customers_out",
        "total_percent_customers_out",
        "total_outage_count",
        "total_customers_served",
    ],
)
async def test_total_update_timeout(hass: HomeAssistant, sensor) -> None:
    """Test if it raises an error when there is a timeout."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)
    with patch(
        "peco.PecoOutageApi.get_outage_totals",
        side_effect=asyncio.TimeoutError(),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "sensor",
    [
        "bucks_customers_out",
        "bucks_percent_customers_out",
        "bucks_outage_count",
        "bucks_customers_served",
    ],
)
async def test_http_error(hass: HomeAssistant, sensor: str) -> None:
    """Test if it raises an error when an abnormal status code is returned."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.get_outage_count",
        side_effect=HttpError(),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "sensor",
    [
        "bucks_customers_out",
        "bucks_percent_customers_out",
        "bucks_outage_count",
        "bucks_customers_served",
    ],
)
async def test_bad_json(hass: HomeAssistant, sensor: str) -> None:
    """Test if it raises an error when abnormal JSON is returned."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=COUNTY_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.get_outage_count",
        side_effect=BadJSONError(),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
