"""Common fixtures for sleepiq tests."""

import pytest

from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture

BASE_URL = "https://prod-api.sleepiq.sleepnumber.com/rest/"


@pytest.fixture
def requests_mock_fixture(request, requests_mock):
    """Mock responses for SleepIQ API."""
    requests_mock.put(
        BASE_URL + "login", text=load_fixture("login.json", integration=DOMAIN)
    )
    requests_mock.get(
        BASE_URL + "bed?_k=0987",
        text=load_fixture(f"bed{request.param}.json", integration=DOMAIN),
    )
    requests_mock.get(
        BASE_URL + "sleeper?_k=0987",
        text=load_fixture("sleeper.json", integration=DOMAIN),
    )
    requests_mock.get(
        BASE_URL + "bed/familyStatus?_k=0987",
        text=load_fixture(f"familystatus{request.param}.json", integration=DOMAIN),
    )
    return request.param


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_SCAN_INTERVAL: 60,
    }


@pytest.fixture
def config_entry(config_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )


@pytest.fixture
async def setup_entry(hass, config_entry):
    """Initialize the config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
