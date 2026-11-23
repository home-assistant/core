"""Test Météo France init."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests import HTTPError, RequestException, Response

from homeassistant.components.meteo_france.const import (
    CONF_CITY,
    DOMAIN,
    METEO_FRANCE_DATA,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.meteo_france.PLATFORMS", []):
        yield


def _second_city(hass: HomeAssistant) -> MockConfigEntry:
    """Return a second entry for a different city in the same department."""
    entry_data = {
        CONF_CITY: "Le Grand-Bornand",
        CONF_LATITUDE: 45.94179,
        CONF_LONGITUDE: 6.42794,
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        unique_id=f"{entry_data[CONF_LATITUDE], entry_data[CONF_LONGITUDE]}",
        title=entry_data[CONF_CITY],
        data=entry_data,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_only_one_city_per_department_provides_alerts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the second city in a department does not also provide alerts."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.alert_coordinator is not None

    second_entry = _second_city(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED
    assert second_entry.runtime_data.alert_coordinator is None


async def test_unload_releases_the_department(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test unloading releases the department so another city can claim it."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.data[METEO_FRANCE_DATA]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data[METEO_FRANCE_DATA]

    second_entry = _second_city(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.runtime_data.alert_coordinator is not None


async def test_unload_the_city_with_alerts_first(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a city without alerts unloads after the city with alerts."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    second_entry = _second_city(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert await hass.config_entries.async_unload(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_closes_the_session(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_requests: MagicMock,
) -> None:
    """Test unloading closes the HTTP session of the client."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    patch_requests.session.close.assert_called_once()


@pytest.mark.parametrize(
    "method",
    ["get_forecast", "get_rain", "get_warning_current_phenomenons"],
)
async def test_setup_retry_when_a_request_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_requests: MagicMock,
    method: str,
) -> None:
    """Test setup is retried when Météo-France cannot be reached."""
    getattr(patch_requests, method).side_effect = RequestException

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_without_rain_forecast(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_requests: MagicMock,
) -> None:
    """Test setup succeeds without the rain coordinator for a place without rain."""
    response = Response()
    response.status_code = 400
    patch_requests.get_rain.side_effect = HTTPError(response=response)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.rain_coordinator is None


async def test_failed_alert_request_does_not_claim_the_department(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_requests: MagicMock,
) -> None:
    """Test the department stays free when the alerts cannot be fetched."""
    patch_requests.get_warning_current_phenomenons.side_effect = RequestException

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data[METEO_FRANCE_DATA]
