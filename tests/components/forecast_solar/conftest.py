"""Fixtures for Forecast.Solar integration tests."""

import datetime
import json
from typing import Generator
from unittest.mock import MagicMock, patch

from forecast_solar import Estimate
import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(autouse=True)
async def mock_persistent_notification(hass: HomeAssistant) -> None:
    """Set up component for persistent notifications."""
    await async_setup_component(hass, "persistent_notification", {})


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Green House",
        unique_id="unique",
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING: 0.5,
        },
    )


class MockDateTime(datetime.datetime):
    """Patch time to a specific point."""

    @classmethod
    def now(cls, *args, **kwargs):
        """Overload datetime.datetime.now."""
        return cls(2021, 6, 26, 12, 39, 8, 337970, tzinfo=datetime.timezone.utc)

    @classmethod
    def replace(cls, *args, **kwargs):
        """Overload datetime.datetime.replace."""
        return cls(2021, 6, 26, 12, 39, 59, 337970, tzinfo=datetime.timezone.utc)


@pytest.fixture
def mock_forecast_solar() -> Generator[None, MagicMock, None]:
    """Return a mocked Forecast.Solar client."""
    with patch("forecast_solar.models.datetime", MockDateTime,), patch(
        "homeassistant.components.forecast_solar.ForecastSolar", autospec=True
    ) as forecast_solar_mock:
        forecast_solar = forecast_solar_mock.return_value

        estimate = Estimate.from_dict(
            json.loads(load_fixture("forecast_solar/estimate.json"))
        )

        forecast_solar.estimate.return_value = estimate
        yield forecast_solar


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> MockConfigEntry:
    """Set up the Forecast.Solar integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
