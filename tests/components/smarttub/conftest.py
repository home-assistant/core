"""Common fixtures for smarttub tests."""

from unittest.mock import create_autospec, patch

import pytest
import smarttub

from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"}


@pytest.fixture
def config_entry(config_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )


@pytest.fixture
async def setup_component(hass):
    """Set up the component."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture(name="spa")
def mock_spa():
    """Mock a smarttub.Spa."""

    mock_spa = create_autospec(smarttub.Spa, instance=True)
    mock_spa.id = "mockspa1"
    mock_spa.brand = "mockbrand1"
    mock_spa.model = "mockmodel1"
    mock_spa.get_status.return_value = {
        "setTemperature": 39,
        "water": {"temperature": 38},
        "heater": "ON",
        "heatMode": "AUTO",
        "state": "NORMAL",
        "primaryFiltration": {
            "cycle": 1,
            "duration": 4,
            "lastUpdated": "2021-01-20T11:38:57.014Z",
            "mode": "NORMAL",
            "startHour": 2,
            "status": "INACTIVE",
        },
        "secondaryFiltration": {
            "lastUpdated": "2020-07-09T19:39:52.961Z",
            "mode": "AWAY",
            "status": "INACTIVE",
        },
        "flowSwitch": "OPEN",
        "ozone": "OFF",
        "uv": "OFF",
        "blowoutCycle": "INACTIVE",
        "cleanupCycle": "INACTIVE",
    }

    mock_circulation_pump = create_autospec(smarttub.SpaPump, instance=True)
    mock_circulation_pump.id = "CP"
    mock_circulation_pump.spa = mock_spa
    mock_circulation_pump.state = smarttub.SpaPump.PumpState.OFF
    mock_circulation_pump.type = smarttub.SpaPump.PumpType.CIRCULATION

    mock_jet_off = create_autospec(smarttub.SpaPump, instance=True)
    mock_jet_off.id = "P1"
    mock_jet_off.spa = mock_spa
    mock_jet_off.state = smarttub.SpaPump.PumpState.OFF
    mock_jet_off.type = smarttub.SpaPump.PumpType.JET

    mock_jet_on = create_autospec(smarttub.SpaPump, instance=True)
    mock_jet_on.id = "P2"
    mock_jet_on.spa = mock_spa
    mock_jet_on.state = smarttub.SpaPump.PumpState.HIGH
    mock_jet_on.type = smarttub.SpaPump.PumpType.JET

    mock_spa.get_pumps.return_value = [mock_circulation_pump, mock_jet_off, mock_jet_on]

    return mock_spa


@pytest.fixture(name="account")
def mock_account(spa):
    """Mock a SmartTub.Account."""

    mock_account = create_autospec(smarttub.Account, instance=True)
    mock_account.id = "mockaccount1"
    mock_account.get_spas.return_value = [spa]
    return mock_account


@pytest.fixture(name="smarttub_api", autouse=True)
def mock_api(account, spa):
    """Mock the SmartTub API."""

    with patch(
        "homeassistant.components.smarttub.controller.SmartTub",
        autospec=True,
    ) as api_class_mock:
        api_mock = api_class_mock.return_value
        api_mock.get_account.return_value = account
        yield api_mock


@pytest.fixture
async def setup_entry(hass, config_entry):
    """Initialize the config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
