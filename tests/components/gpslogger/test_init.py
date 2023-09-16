"""The tests the for GPSLogger device tracker platform."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import gpslogger, zone
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.gpslogger import DOMAIN, TRACKER_UPDATE
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""


@pytest.fixture
async def gpslogger_client(event_loop, hass, hass_client_no_auth):
    """Mock client for GPSLogger (unauthenticated)."""

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    await hass.async_block_till_done()

    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        return await hass_client_no_auth()


@pytest.fixture(autouse=True)
async def setup_zones(event_loop, hass):
    """Set up Zone config in HA."""
    assert await async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": {
                "name": "Home",
                "latitude": HOME_LATITUDE,
                "longitude": HOME_LONGITUDE,
                "radius": 100,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def webhook_id(hass, gpslogger_client):
    """Initialize the GPSLogger component and get the webhook_id."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    return result["result"].data["webhook_id"]


async def test_missing_data(hass: HomeAssistant, gpslogger_client, webhook_id) -> None:
    """Test missing data."""
    url = f"/api/webhook/{webhook_id}"

    data = {"latitude": 1.0, "longitude": 1.1, "device": "123"}

    # No data
    req = await gpslogger_client.post(url)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy["latitude"]
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy["device"]
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_enter_and_exit(
    hass: HomeAssistant, gpslogger_client, webhook_id
) -> None:
    """Test when there is a known zone."""
    url = f"/api/webhook/{webhook_id}"

    data = {"latitude": HOME_LATITUDE, "longitude": HOME_LONGITUDE, "device": "123"}

    # Enter the Home
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}").state
    assert state_name == STATE_HOME

    # Enter Home again
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}").state
    assert state_name == STATE_HOME

    data["longitude"] = 0
    data["latitude"] = 0

    # Enter Somewhere else
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}").state
    assert state_name == STATE_NOT_HOME

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == 1

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 1


async def test_enter_with_attrs(
    hass: HomeAssistant, gpslogger_client, webhook_id
) -> None:
    """Test when additional attributes are present."""
    url = f"/api/webhook/{webhook_id}"

    data = {
        "latitude": 1.0,
        "longitude": 1.1,
        "device": "123",
        "accuracy": 10.5,
        "battery": 10,
        "speed": 100,
        "direction": 105.32,
        "altitude": 102,
        "provider": "gps",
        "activity": "running",
    }

    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}")
    assert state.state == STATE_NOT_HOME
    assert state.attributes["gps_accuracy"] == 10.5
    assert state.attributes["battery_level"] == 10.0
    assert state.attributes["speed"] == 100.0
    assert state.attributes["direction"] == 105.32
    assert state.attributes["altitude"] == 102.0
    assert state.attributes["provider"] == "gps"
    assert state.attributes["activity"] == "running"

    data = {
        "latitude": HOME_LATITUDE,
        "longitude": HOME_LONGITUDE,
        "device": "123",
        "accuracy": 123,
        "battery": 23,
        "speed": 23,
        "direction": 123,
        "altitude": 123,
        "provider": "gps",
        "activity": "idle",
    }

    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}")
    assert state.state == STATE_HOME
    assert state.attributes["gps_accuracy"] == 123
    assert state.attributes["battery_level"] == 23
    assert state.attributes["speed"] == 23
    assert state.attributes["direction"] == 123
    assert state.attributes["altitude"] == 123
    assert state.attributes["provider"] == "gps"
    assert state.attributes["activity"] == "idle"


@pytest.mark.xfail(
    reason="The device_tracker component does not support unloading yet."
)
async def test_load_unload_entry(
    hass: HomeAssistant, gpslogger_client, webhook_id
) -> None:
    """Test that the appropriate dispatch signals are added and removed."""
    url = f"/api/webhook/{webhook_id}"
    data = {"latitude": HOME_LATITUDE, "longitude": HOME_LONGITUDE, "device": "123"}

    # Enter the Home
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.{data['device']}").state
    assert state_name == STATE_HOME
    assert len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE]) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await gpslogger.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert not hass.data[DATA_DISPATCHER][TRACKER_UPDATE]
