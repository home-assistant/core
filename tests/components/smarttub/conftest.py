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
    full_status = smarttub.SpaStateFull(
        mock_spa,
        {
            "setTemperature": 39,
            "water": {"temperature": 38},
            "heater": "ON",
            "online": True,
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
            "lights": [],
            "pumps": [],
        },
    )
    mock_spa.get_status_full.return_value = full_status

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

    full_status.pumps = [mock_circulation_pump, mock_jet_off, mock_jet_on]

    mock_light_off = create_autospec(smarttub.SpaLight, instance=True)
    mock_light_off.spa = mock_spa
    mock_light_off.zone = 1
    mock_light_off.intensity = 0
    mock_light_off.mode = smarttub.SpaLight.LightMode.OFF

    mock_light_on = create_autospec(smarttub.SpaLight, instance=True)
    mock_light_on.spa = mock_spa
    mock_light_on.zone = 2
    mock_light_on.intensity = 50
    mock_light_on.mode = smarttub.SpaLight.LightMode.PURPLE

    full_status.lights = [mock_light_off, mock_light_on]

    mock_filter_reminder = create_autospec(smarttub.SpaReminder, instance=True)
    mock_filter_reminder.id = "FILTER01"
    mock_filter_reminder.name = "MyFilter"
    mock_filter_reminder.remaining_days = 2
    mock_filter_reminder.snoozed = False

    mock_spa.get_reminders.return_value = [mock_filter_reminder]

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
