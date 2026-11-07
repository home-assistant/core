"""Test the TFA.me integration: conftest.py."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.tfa_me.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, MockConfigEntry, load_json_object_fixture


@pytest.fixture
def tfa_me_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a default TFA.me config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10"},
        unique_id="05b3e4e44",
        title="TFA.me Station '05B3E4E44'",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_tfa_me_client() -> Generator[AsyncMock]:
    """Mock the TFA.me client network request."""
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new_callable=AsyncMock,
    ) as mock_get_sensors:
        mock_get_sensors.return_value = STATION_DATA_JSON
        yield mock_get_sensors


# Original JSON data from a TFA.me station for snapshot testing
STATION_DATA_JSON = load_json_object_fixture("station_data.json", DOMAIN)
