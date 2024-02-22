"""Test the PECO Outage Counter init file."""
from unittest.mock import patch

from peco import (
    AlertResults,
    BadJSONError,
    HttpError,
    OutageResults,
    UnresponsiveMeterError,
)
import pytest

from homeassistant.components.peco.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {"county": "TOTAL"}
COUNTY_ENTRY_DATA = {"county": "BUCKS"}
INVALID_COUNTY_DATA = {"county": "INVALID"}
METER_DATA = {"county": "BUCKS", "phone_number": "1234567890"}


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
        side_effect=TimeoutError(),
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
        side_effect=TimeoutError(),
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


async def test_unresponsive_meter_error(hass: HomeAssistant) -> None:
    """Test if it raises an error when the meter will not respond."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=METER_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.meter_check",
        side_effect=UnresponsiveMeterError(),
    ), patch(
        "peco.PecoOutageApi.get_outage_count",
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
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.meter_status") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_meter_http_error(hass: HomeAssistant) -> None:
    """Test if it raises an error when there is an HTTP error."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=METER_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.meter_check",
        side_effect=HttpError(),
    ), patch(
        "peco.PecoOutageApi.get_outage_count",
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
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.meter_status") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_meter_bad_json(hass: HomeAssistant) -> None:
    """Test if it raises an error when there is bad JSON."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=METER_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.meter_check",
        side_effect=BadJSONError(),
    ), patch(
        "peco.PecoOutageApi.get_outage_count",
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
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.meter_status") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_meter_timeout(hass: HomeAssistant) -> None:
    """Test if it raises an error when there is a timeout."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=METER_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.meter_check",
        side_effect=TimeoutError(),
    ), patch(
        "peco.PecoOutageApi.get_outage_count",
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
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.meter_status") is None
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_meter_data(hass: HomeAssistant) -> None:
    """Test if the meter returns the value successfully."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=METER_DATA)
    config_entry.add_to_hass(hass)

    with patch(
        "peco.PecoOutageApi.meter_check",
        return_value=True,
    ), patch(
        "peco.PecoOutageApi.get_outage_count",
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

    assert hass.states.get("binary_sensor.meter_status") is not None
    assert hass.states.get("binary_sensor.meter_status").state == "on"
    assert config_entry.state == ConfigEntryState.LOADED
