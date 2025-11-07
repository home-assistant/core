"""Test the TFA.me integration: test of config_flow (options flow).py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tfa_me.config_flow import OptionsFlowHandler
from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.components.tfa_me.coordinator import TFAmeDataCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant):
    """Create a mock config entry in HA."""
    entry = AsyncMock()
    entry.entry_id = "1234"
    entry.runtime_data = mock_coordinator
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mocked coordinator."""
    coordinator = AsyncMock()
    coordinator.host = "192.168.1.10"
    coordinator.interval = 120
    coordinator.name_with_station_id = False
    coordinator.first_init = 0
    coordinator.gateway_id = "017654321"
    coordinator.sensor_entity_list = []
    coordinator.data = {}
    return coordinator


def create_default_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create default mock config entry."""
    default_entry_x = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME_WITH_STATION_ID: True,
        },
        unique_id="test-1234",
    )
    default_entry_x.add_to_hass(hass)
    return default_entry_x


# ----------------------------
# Tests
# ----------------------------


@pytest.mark.asyncio
async def test_setup_entry_bad_ip(hass: HomeAssistant) -> None:
    """Test entry setup with bad IP."""

    entry_x = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: 1234,  # Bad IP, no valid MDNS
            CONF_NAME_WITH_STATION_ID: True,
        },
        unique_id="test-1234",
    )
    entry_x.add_to_hass(hass)

    # Patch coordinator
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeDataCoordinator._async_update_data",
        side_effect=Exception("invalid ip"),
    ):
        result = await hass.config_entries.async_setup(entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is False


@pytest.mark.asyncio
async def test_options_flow_action_rain(hass: HomeAssistant) -> None:
    """Test the action_rain option in OptionsFlowHandler."""

    # Fake JSON reply from gateway
    fake_json = {"gateway_id": "012345678", "sensors": []}

    # Create mock config entry
    cfg_entry_x = create_default_mock_entry(hass)
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED

    # Create a TFA.me data coordinator
    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=cfg_entry_x,
        host="127.0.0.1",
        interval=timedelta(30),
        name_with_station_id=False,
    )
    # Add dummy entity and coordinator data for a rain value
    coordinator.sensor_entity_list = ["sensor.a12345678_rain_rel"]
    now = datetime.now().timestamp()
    coordinator.data = {
        "sensor.a12345678_rain_rel": {
            "sensor_id": "a12345678",
            "gateway_id": "017654321",
            "sensor_name": "A12345678",
            "measurement": "rain_rel",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": True,
        },
    }

    # Add coordinator to hass.data
    hass.data.setdefault(DOMAIN, {})[cfg_entry_x.entry_id] = coordinator

    # Register dummy services in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )
    hass.services.async_register("homeassistant", "update_entity", lambda call: None)

    # Start OptionsFlow for action "action_rain" via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        cfg_entry_x.entry_id,
        context={"source": "user"},
        data={"select_option": "action_rain"},
    )

    # Assertions
    assert result["type"] == "create_entry"
    assert result["title"] == "action_rain"
    assert result["data"]["action_rain"] is True


@pytest.mark.asyncio
async def test_options_flow_show_main_menu(
    hass: HomeAssistant, mock_config_entry, mock_coordinator
) -> None:
    """Test that OptionsFlowHandler shows main options menu correctly."""

    await mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = mock_coordinator

    flow = OptionsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert "select_option" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_action_rain_show_form_direct_call(hass: HomeAssistant) -> None:
    """Call async_step_action_rain with user_input=None and await show_form."""

    cfg_entry_x = create_default_mock_entry(hass)

    # Create Flow-Handler and set hass and config_entry (Test-only)
    flow = OptionsFlowHandler()
    flow.hass = hass
    result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
    await hass.async_block_till_done()

    # Call with user_input = None -> should show the form
    result = await flow.async_step_action_rain(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "action_rain"
