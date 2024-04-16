"""The tests the for Traccar device tracker platform."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import traccar, zone
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.traccar import DOMAIN, TRACKER_UPDATE
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""


@pytest.fixture(name="client")
async def traccar_client(hass, hass_client_no_auth):
    """Mock client for Traccar (unauthenticated)."""

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    await hass.async_block_till_done()

    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        return await hass_client_no_auth()


@pytest.fixture(autouse=True)
async def setup_zones(hass):
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


@pytest.fixture(name="webhook_id")
async def webhook_id_fixture(hass, client):
    """Initialize the Traccar component and get the webhook_id."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    return result["result"].data["webhook_id"]


async def test_missing_data(hass: HomeAssistant, client, webhook_id) -> None:
    """Test missing data."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": "1.0", "lon": "1.1", "id": "123"}

    # No data
    req = await client.post(url)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy["lat"]
    req = await client.post(url, params=copy)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy["id"]
    req = await client.post(url, params=copy)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass: HomeAssistant, client, webhook_id) -> None:
    """Test when there is a known zone."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": str(HOME_LATITUDE), "lon": str(HOME_LONGITUDE), "id": "123"}

    # Enter the Home
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert state_name == STATE_HOME

    # Enter Home again
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert state_name == STATE_HOME

    data["lon"] = 0
    data["lat"] = 0

    # Enter Somewhere else
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert state_name == STATE_NOT_HOME

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == 1

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 1


async def test_enter_with_attrs(hass: HomeAssistant, client, webhook_id) -> None:
    """Test when additional attributes are present."""
    url = f"/api/webhook/{webhook_id}"
    data = {
        "timestamp": 123456789,
        "lat": "1.0",
        "lon": "1.1",
        "id": "123",
        "accuracy": "10.5",
        "batt": 10,
        "speed": 100,
        "bearing": "105.32",
        "altitude": 102,
        "charge": "true",
    }

    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"]))
    assert state.state == STATE_NOT_HOME
    assert state.attributes["gps_accuracy"] == 10.5
    assert state.attributes["battery_level"] == 10.0
    assert state.attributes["speed"] == 100.0
    assert state.attributes["bearing"] == 105.32
    assert state.attributes["altitude"] == 102.0
    assert "charge" not in state.attributes

    data = {
        "lat": str(HOME_LATITUDE),
        "lon": str(HOME_LONGITUDE),
        "id": "123",
        "accuracy": 123,
        "batt": 23,
        "speed": 23,
        "bearing": 123,
        "altitude": 123,
    }

    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"]))
    assert state.state == STATE_HOME
    assert state.attributes["gps_accuracy"] == 123
    assert state.attributes["battery_level"] == 23
    assert state.attributes["speed"] == 23
    assert state.attributes["bearing"] == 123
    assert state.attributes["altitude"] == 123


async def test_two_devices(hass: HomeAssistant, client, webhook_id) -> None:
    """Test updating two different devices."""
    url = f"/api/webhook/{webhook_id}"

    data_device_1 = {"lat": "1.0", "lon": "1.1", "id": "device_1"}

    # Exit Home
    req = await client.post(url, params=data_device_1)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK

    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_1["id"]))
    assert state.state == "not_home"

    # Enter Home
    data_device_2 = dict(data_device_1)
    data_device_2["lat"] = str(HOME_LATITUDE)
    data_device_2["lon"] = str(HOME_LONGITUDE)
    data_device_2["id"] = "device_2"
    req = await client.post(url, params=data_device_2)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK

    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_2["id"]))
    assert state.state == "home"
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_1["id"]))
    assert state.state == "not_home"


@pytest.mark.xfail(
    reason="The device_tracker component does not support unloading yet."
)
async def test_load_unload_entry(hass: HomeAssistant, client, webhook_id) -> None:
    """Test that the appropriate dispatch signals are added and removed."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": str(HOME_LATITUDE), "lon": str(HOME_LONGITUDE), "id": "123"}

    # Enter the Home
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert state_name == STATE_HOME
    assert len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE]) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await traccar.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert not hass.data[DATA_DISPATCHER][TRACKER_UPDATE]
