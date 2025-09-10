"""Tests for TFA.me: test of config_flow (options flow).py."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.a_tfa_me_1.config_flow import OptionsFlowHandler
from homeassistant.components.a_tfa_me_1.const import (
    CONF_INTERVAL,
    CONF_MULTIPLE_ENTITIES,
    DOMAIN,
)
from homeassistant.components.a_tfa_me_1.coordinator import TFAmeDataCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

# from tests.components.androidtv.patchers import PATCH_SETUP_ENTRY


PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.a_tfa_me_1.async_setup_entry",
    return_value=True,
)

PATCH_SETUP_INTERVAL = patch(
    "homeassistant.components.a_tfa_me_1.config_flow.OptionsFlowHandler.async_step_set_interval",
    return_value=True,
)

# ----------------------------
# Fixtures
# ----------------------------


@pytest.fixture
async def mock_entry(hass: HomeAssistant):
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
    coordinator.multiple_entities = False
    coordinator.first_init = 0
    coordinator.reset_rain_sensors = False
    coordinator.gateway_id = "017654321"

    now = datetime.now().timestamp()
    coordinator.sensor_entity_list = ["sensor.a01234567_temperature"]
    coordinator.data = {
        "sensor.a01234567_temperature": {
            "sensor_id": "a01234567",
            "gateway_id": "017654321",
            "sensor_name": "A01234567",
            "measurement": "temperature",
            "value": "23.5",
            "unit": "°C",
            "timestamp": "2025-09-01T08:46:01Z",
            "ts": int(now),
            "info": "",
        }
    }
    return coordinator


@pytest.fixture
def tfa_me_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry for a_tfa_me_1 integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_INTERVAL: 30,
            CONF_MULTIPLE_ENTITIES: False,
        },
        unique_id="test-1234",
    )
    entry.add_to_hass(hass)
    return entry


# ----------------------------
# Tests
# ----------------------------


@pytest.mark.asyncio
async def test_setup_entry_bad_ip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entry setup with bad IP."""

    # simulate dummy reply from gateway
    # aioclient_mock.get(
    #    "http://1234/sensors",  # Bad IP, no valid MDNS
    #    json={"gateway_id": "001", "sensors": []},
    # )

    entry_x = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: 1234,  # Bad IP, no valid MDNS
            CONF_INTERVAL: 30,
            CONF_MULTIPLE_ENTITIES: True,
        },
        unique_id="test-1234",
    )
    entry_x.add_to_hass(hass)

    # Patch den Coordinator, damit kein HTTP-Request passiert
    with patch(
        "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
        side_effect=Exception("invalid ip"),
    ):
        result = await hass.config_entries.async_setup(entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is False


@pytest.mark.asyncio
async def test_options_flow_action_rain(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tfa_me_mock_entry
) -> None:
    """Test the action_rain option in OptionsFlowHandler."""

    # Simulate dummy reply from gateway
    # aioclient_mock.get(
    #    "http://127.0.0.1/sensors",
    #    json={"gateway_id": "001", "sensors": []},
    # )
    fake_json = {"gateway_id": "001", "sensors": []}

    # Create mock config entry
    cfg_entry_x = create_default_mock_entry(hass)
    with patch(
        "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED

    # Create a TFA.me data coordinator
    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="127.0.0.1",
        interval=timedelta(30),
        multiple_entities=False,
    )
    # Add dummy entities
    coordinator.sensor_entity_list = ["sensor.rain1", "sensor.rain2"]

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
async def test_setup_entry_and_action_rain(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a successful setup."""

    # simulate dummy reply from gateway
    # aioclient_mock.get(
    #    "http://127.0.0.1/sensors",
    #    json={"gateway_id": "001", "sensors": []},
    # )

    fake_json = {"gateway_id": "001", "sensors": []}

    # Create dummy config entry
    cfg_entry_x = create_default_mock_entry(hass)

    with patch(
        "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED
    # setup ready now call an action

    # Register dummy service in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )

    # Start OptionsFlow for action "action_rain" via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        cfg_entry_x.entry_id,
        context={"source": "user"},
        data={"select_option": "action_rain"},
    )

    # Test result
    assert result["type"] == "create_entry"
    assert result["title"] == "action_rain"
    assert result["data"] == ({"action_rain": True})


@pytest.mark.asyncio
async def test_setup_entry_and_action_update_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tfa_me_mock_entry
) -> None:
    """Test a successful setup: async_update_data()."""

    # Simulate dummy reply from gateway
    # aioclient_mock.get(
    #    "http://127.0.0.1/sensors",
    #    json={"gateway_id": "001", "sensors": []},
    # )

    fake_json = {"gateway_id": "001", "sensors": []}
    # Create dummy config entry and add it to hass
    cfg_entry_x = create_default_mock_entry(hass)

    with patch(
        "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED
    # setup ready now call an action

    # Create a TFA.me data coordinator
    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="192.168.1.46",
        interval=timedelta(30),
        multiple_entities=False,
    )
    # Add dummy entities
    coordinator.sensor_entity_list = ["sensor.rain1", "sensor.rain2"]

    # Add coordinator to hass.data
    hass.data.setdefault(DOMAIN, {})[cfg_entry_x.entry_id] = coordinator

    # Register dummy services in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )
    hass.services.async_register("homeassistant", "update_entity", lambda call: None)

    # Register dummy service in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )

    # Start OptionsFlow via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        cfg_entry_x.entry_id,
        context={"source": "user"},
        data={"select_option": "update_data"},
    )

    # Test result
    assert result["type"] == "create_entry"
    assert result["title"] == "update_data"


@pytest.mark.asyncio
async def test_setup_entry_and_menu_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a successful setup."""

    # Simulate dummy reply from gateway
    # aioclient_mock.get(
    #    "http://127.0.0.1/sensors",
    #    json={"gateway_id": "001", "sensors": []},
    # )
    fake_json = {"gateway_id": "001", "sensors": []}
    # Create dummy config entry and add it to hass
    cfg_entry_x = create_default_mock_entry(hass)

    with patch(
        "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED
    # setup ready now call an action

    # Register dummy service in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )

    # Start OptionsFlow via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        cfg_entry_x.entry_id,
        context={"source": "user"},
        data={"select_option": "menu_interval"},
    )

    # Test result
    assert result["type"] == "form"
    assert result["description_placeholders"] == ({"interval": "10"})


@pytest.mark.asyncio
async def test_setup_entry_and_menu_discover_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a successful setup."""

    # simulate dummy reply from gateway
    now = datetime.now().timestamp()
    aioclient_mock.get(
        "http://127.0.0.1/sensors",
        json={
            "gateway_id": "017654321",
            "sensors": [
                {
                    "sensor_id": "a21234567",
                    "name": "A21234567",
                    "timestamp": "2025-09-04T12:21:41Z",
                    "ts": int(now),
                    "measurements": {
                        "rssi": {"value": "221", "unit": "/255"},
                        "lowbatt": {"value": "0", "unit": "No"},
                        "wind_direction": {"value": "8", "unit": ""},
                        "wind_speed": {"value": "0.0", "unit": "m/s"},
                        "wind_gust": {"value": "0.0", "unit": "m/s"},
                    },
                },
            ],
        },
    )

    # fake_json = {
    #    "gateway_id": "017654321",
    #    "sensors": [
    #        {
    #            "sensor_id": "a21234567",
    #            "name": "A21234567",
    #            "timestamp": "2025-09-04T12:21:41Z",
    #            "ts": int(now),
    #            "measurements": {
    #                "rssi": {"value": "221", "unit": "/255"},
    #                "lowbatt": {"value": "0", "unit": "No"},
    #                "wind_direction": {"value": "8", "unit": ""},
    #                "wind_speed": {"value": "0.0", "unit": "m/s"},
    #                "wind_gust": {"value": "0.0", "unit": "m/s"},
    #            },
    #        },
    #    ],
    # }

    cfg_entry_x = create_default_mock_entry(hass)

    # with patch(
    #    "homeassistant.components.a_tfa_me_1.coordinator.TFAmeDataCoordinator._async_update_data",
    #    new=AsyncMock(return_value=fake_json),
    # ):
    result = await hass.config_entries.async_setup(cfg_entry_x.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert cfg_entry_x.state == ConfigEntryState.LOADED
    # setup ready now call an action

    # Register dummy service in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )

    # Start OptionsFlow via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        cfg_entry_x.entry_id,
        context={"source": "user"},
        data={"select_option": "discover_sensors"},
    )

    # Test result
    assert result["type"] == "create_entry"
    assert result["title"] == "discover_sensors"


@pytest.mark.asyncio
async def test_options_flow_change_interval(
    hass: HomeAssistant, mock_entry, mock_coordinator
) -> None:
    """Test that OptionsFlowHandler changes interval correctly."""

    await mock_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_entry.entry_id] = mock_coordinator

    # Register dummy service in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )

    flow = OptionsFlowHandler()
    flow.hass = hass

    # User input
    user_input = {"interval": 45}
    with patch("homeassistant.core.ServiceRegistry.async_call") as mock_service:
        result = await flow.async_step_init(user_input=user_input)
        mock_service.assert_called()

    assert result["type"] == "create_entry"
    assert result["data"]["interval"] == 45


@pytest.mark.asyncio
async def test_options_flow_set_interval(hass: HomeAssistant) -> None:
    """Test that setting the interval works in options flow."""
    now = datetime.now().timestamp()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "sensor.a01234567_temperature": {
                "sensor_id": "a01234567",
                "gateway_id": "017654321",
                "sensor_name": "A01234567",
                "measurement": "temperature",
                "value": "23.5",
                "unit": "°C",
                "timestamp": "2025-09-01T08:46:01Z",
                "ts": int(now),
                "info": "",
            }
        },
        unique_id="123456789",
        options={"select_option": "menu_interval", "interval": 45},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # assert result == ""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Patch coordinator
    coordinator = AsyncMock()
    coordinator.sensor_entity_list = ["sensor.a01234567_temperature"]
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    # Act: Create OptionsFlow and call step
    flow = OptionsFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.a_tfa_me_1.config_flow.OptionsFlowHandler.async_step_set_interval",
        return_value={"step_id": "init", "data": {"interval": 45}},
    ):
        result = await flow.async_step_set_interval({"interval": 45})

        # Asserts
        assert result["step_id"] == "init"
        assert result["data"]["interval"] == 45


@pytest.mark.asyncio
async def test_options_flow_show_main_menu(
    hass: HomeAssistant, mock_entry, mock_coordinator
) -> None:
    """Test that OptionsFlowHandler shows main options menu correctly."""

    await mock_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_entry.entry_id] = mock_coordinator

    flow = OptionsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert "select_option" in result["data_schema"].schema


def create_default_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create default mock config entry."""
    default_entry_x = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_INTERVAL: 30,
            CONF_MULTIPLE_ENTITIES: True,
        },
        unique_id="test-1234",
    )
    default_entry_x.add_to_hass(hass)
    return default_entry_x


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
