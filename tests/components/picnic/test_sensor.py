"""The tests for the Picnic sensor platform."""
import copy
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant import config_entries
from homeassistant.components.picnic import const
from homeassistant.components.picnic.const import CONF_COUNTRY_CODE, SENSOR_TYPES
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CURRENCY_EURO,
    DEVICE_CLASS_TIMESTAMP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed

DEFAULT_USER_RESPONSE = {
    "user_id": "295-6y3-1nf4",
    "firstname": "User",
    "lastname": "Name",
    "address": {
        "house_number": 123,
        "house_number_ext": "a",
        "postcode": "4321 AB",
        "street": "Commonstreet",
        "city": "Somewhere",
    },
    "total_deliveries": 123,
    "completed_deliveries": 112,
}
DEFAULT_CART_RESPONSE = {
    "items": [],
    "delivery_slots": [
        {
            "slot_id": "611a3b074872b23576bef456a",
            "window_start": "2021-03-03T14:45:00.000+01:00",
            "window_end": "2021-03-03T15:45:00.000+01:00",
            "cut_off_time": "2021-03-02T22:00:00.000+01:00",
            "minimum_order_value": 3500,
        },
    ],
    "selected_slot": {"slot_id": "611a3b074872b23576bef456a", "state": "EXPLICIT"},
    "total_count": 10,
    "total_price": 2535,
}
DEFAULT_DELIVERY_RESPONSE = {
    "delivery_id": "z28fjso23e",
    "creation_time": "2021-02-24T21:48:46.395+01:00",
    "slot": {
        "slot_id": "602473859a40dc24c6b65879",
        "hub_id": "AMS",
        "window_start": "2021-02-26T20:15:00.000+01:00",
        "window_end": "2021-02-26T21:15:00.000+01:00",
        "cut_off_time": "2021-02-25T22:00:00.000+01:00",
        "minimum_order_value": 3500,
    },
    "eta2": {
        "start": "2021-02-26T20:54:00.000+01:00",
        "end": "2021-02-26T21:14:00.000+01:00",
    },
    "status": "COMPLETED",
    "delivery_time": {
        "start": "2021-02-26T20:54:05.221+01:00",
        "end": "2021-02-26T20:58:31.802+01:00",
    },
    "orders": [
        {
            "creation_time": "2021-02-24T21:48:46.418+01:00",
            "total_price": 3597,
        },
        {
            "creation_time": "2021-02-25T17:10:26.816+01:00",
            "total_price": 536,
        },
    ],
}

SENSOR_KEYS = [desc.key for desc in SENSOR_TYPES]


@dataclass
class PicnicTestData:
    """A dataclass containing the objects necessary for each test."""

    hass: HomeAssistant
    api_client: MagicMock
    config_entry: ConfigEntry


@pytest.fixture
def picnic(hass: HomeAssistant):
    """Yield a PicnicTestData object with the dependencies needed for each test."""
    with patch("homeassistant.components.picnic.PicnicAPI") as picnic_api:
        api_client = picnic_api()
        api_client.session.auth_token = "3q29fpwhulzes"

        config_entry = _get_config_entry(hass)

        yield PicnicTestData(hass, api_client, config_entry)


def _get_config_entry(hass: HomeAssistant):
    # Add a config entry and setup the integration
    config_data = {
        CONF_ACCESS_TOKEN: "x-original-picnic-auth-token",
        CONF_COUNTRY_CODE: "NL",
    }
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=config_data,
        unique_id="295-6y3-1nf4",
    )
    config_entry.add_to_hass(hass)

    return config_entry


def _get_coordinator(picnic: PicnicTestData):
    return picnic.hass.data[const.DOMAIN][picnic.config_entry.entry_id][
        const.CONF_COORDINATOR
    ]


def _assert_sensor(hass, name, state=None, cls=None, unit=None, disabled=False):
    sensor = hass.states.get(name)
    if disabled:
        assert sensor is None
        return

    assert sensor.state == state
    if cls:
        assert sensor.attributes["device_class"] == cls
    if unit:
        assert sensor.attributes["unit_of_measurement"] == unit

    assert sensor.attributes["attribution"] == "Data provided by Picnic"


async def _setup_platform(
    picnic: PicnicTestData,
    use_default_responses=False,
    enable_all_sensors=True,
):
    """Set up the Picnic sensor platform."""
    if use_default_responses:
        picnic.api_client.get_user.return_value = copy.deepcopy(DEFAULT_USER_RESPONSE)
        picnic.api_client.get_cart.return_value = copy.deepcopy(DEFAULT_CART_RESPONSE)
        picnic.api_client.get_deliveries.return_value = [
            copy.deepcopy(DEFAULT_DELIVERY_RESPONSE)
        ]
        picnic.api_client.get_delivery_position.return_value = {}

    await picnic.hass.config_entries.async_setup(picnic.config_entry.entry_id)
    await picnic.hass.async_block_till_done()

    if enable_all_sensors:
        await _enable_all_sensors(picnic.hass)


async def _enable_all_sensors(hass):
    """Enable all sensors of the Picnic integration."""
    # Enable the sensors
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    for sensor_type in SENSOR_KEYS:
        updated_entry = entity_registry.async_update_entity(
            f"sensor.picnic_{sensor_type}", disabled_by=None
        )
        assert updated_entry.disabled is False
    await hass.async_block_till_done()

    # Trigger a reload of the data
    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=config_entries.RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()


async def test_sensor_setup_platform_not_available(picnic: PicnicTestData):
    """Test the set-up of the sensor platform if API is not available."""

    # Configure mock requests to yield exceptions
    picnic.api_client.get_user.side_effect = requests.exceptions.ConnectionError
    picnic.api_client.get_cart.side_effect = requests.exceptions.ConnectionError
    picnic.api_client.get_deliveries.side_effect = requests.exceptions.ConnectionError
    picnic.api_client.get_delivery_position.side_effect = (
        requests.exceptions.ConnectionError
    )
    await _setup_platform(picnic, enable_all_sensors=False)

    # Assert that sensors are not set up
    assert picnic.hass.states.get("sensor.picnic_selected_slot_max_order_time") is None
    assert picnic.hass.states.get("sensor.picnic_last_order_status") is None
    assert picnic.hass.states.get("sensor.picnic_last_order_total_price") is None


async def test_sensors_setup(picnic: PicnicTestData):
    """Test the default sensor setup behaviour."""
    await _setup_platform(picnic, use_default_responses=True)

    _assert_sensor(picnic.hass, "sensor.picnic_cart_items_count", "10")
    _assert_sensor(
        picnic.hass, "sensor.picnic_cart_total_price", "25.35", unit=CURRENCY_EURO
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_selected_slot_start",
        "2021-03-03T13:45:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_selected_slot_end",
        "2021-03-03T14:45:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_selected_slot_max_order_time",
        "2021-03-02T21:00:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(picnic.hass, "sensor.picnic_selected_slot_min_order_value", "35.0")
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_last_order_slot_start",
        "2021-02-26T19:15:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_last_order_slot_end",
        "2021-02-26T20:15:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_status", "COMPLETED")
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_last_order_eta_start",
        "2021-02-26T19:54:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_last_order_eta_end",
        "2021-02-26T20:14:00+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass,
        "sensor.picnic_last_order_delivery_time",
        "2021-02-26T19:54:05+00:00",
        cls=SensorDeviceClass.TIMESTAMP,
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_total_price", "41.33", unit=CURRENCY_EURO
    )


async def test_sensors_setup_disabled_by_default(picnic: PicnicTestData):
    """Test that some sensors are disabled by default."""
    await _setup_platform(picnic, use_default_responses=True, enable_all_sensors=False)

    _assert_sensor(picnic.hass, "sensor.picnic_cart_items_count", disabled=True)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_slot_start", disabled=True)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_slot_end", disabled=True)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_status", disabled=True)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_total_price", disabled=True)


async def test_sensors_no_selected_time_slot(picnic: PicnicTestData):
    """Test sensor states with no explicit selected time slot."""
    # Adjust cart response
    cart_response = copy.deepcopy(DEFAULT_CART_RESPONSE)
    cart_response["selected_slot"]["state"] = "IMPLICIT"

    # Set mock responses
    picnic.api_client.get_user.return_value = copy.deepcopy(DEFAULT_USER_RESPONSE)
    picnic.api_client.get_cart.return_value = cart_response
    picnic.api_client.get_deliveries.return_value = [
        copy.deepcopy(DEFAULT_DELIVERY_RESPONSE)
    ]
    picnic.api_client.get_delivery_position.return_value = {}
    await _setup_platform(picnic)

    # Assert sensors are unknown
    _assert_sensor(picnic.hass, "sensor.picnic_selected_slot_start", STATE_UNAVAILABLE)
    _assert_sensor(picnic.hass, "sensor.picnic_selected_slot_end", STATE_UNAVAILABLE)
    _assert_sensor(
        picnic.hass, "sensor.picnic_selected_slot_max_order_time", STATE_UNAVAILABLE
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_selected_slot_min_order_value", STATE_UNAVAILABLE
    )


async def test_sensors_last_order_in_future(picnic: PicnicTestData):
    """Test sensor states when last order is not yet delivered."""
    # Adjust default delivery response
    delivery_response = copy.deepcopy(DEFAULT_DELIVERY_RESPONSE)
    del delivery_response["delivery_time"]

    # Set mock responses
    picnic.api_client.get_user.return_value = copy.deepcopy(DEFAULT_USER_RESPONSE)
    picnic.api_client.get_cart.return_value = copy.deepcopy(DEFAULT_CART_RESPONSE)
    picnic.api_client.get_deliveries.return_value = [delivery_response]
    picnic.api_client.get_delivery_position.return_value = {}
    await _setup_platform(picnic)

    # Assert delivery time is not available, but eta is
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_delivery_time", STATE_UNAVAILABLE
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_eta_start", "2021-02-26T19:54:00+00:00"
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_eta_end", "2021-02-26T20:14:00+00:00"
    )


async def test_sensors_use_detailed_eta_if_available(picnic: PicnicTestData):
    """Test sensor states when last order is not yet delivered."""
    # Set-up platform with default mock responses
    await _setup_platform(picnic, use_default_responses=True)

    # Provide a delivery position response with different ETA and remove delivery time from response
    delivery_response = copy.deepcopy(DEFAULT_DELIVERY_RESPONSE)
    del delivery_response["delivery_time"]
    picnic.api_client.get_deliveries.return_value = [delivery_response]
    picnic.api_client.get_delivery_position.return_value = {
        "eta_window": {
            "start": "2021-03-05T10:19:20.452+00:00",
            "end": "2021-03-05T10:39:20.452+00:00",
        }
    }
    await _get_coordinator(picnic).async_refresh()

    # Assert detailed ETA is used
    picnic.api_client.get_delivery_position.assert_called_with(
        delivery_response["delivery_id"]
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_eta_start", "2021-03-05T10:19:20+00:00"
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_eta_end", "2021-03-05T10:39:20+00:00"
    )


async def test_sensors_no_data(picnic: PicnicTestData):
    """Test sensor states when the api only returns empty objects."""
    # Setup platform with default responses
    await _setup_platform(picnic, use_default_responses=True)

    # Change mock responses to empty data and refresh the coordinator
    picnic.api_client.get_user.return_value = {}
    picnic.api_client.get_cart.return_value = None
    picnic.api_client.get_deliveries.return_value = None
    picnic.api_client.get_delivery_position.side_effect = ValueError
    await _get_coordinator(picnic).async_refresh()

    # Assert all default-enabled sensors have STATE_UNAVAILABLE because the last update failed
    assert _get_coordinator(picnic).last_update_success is False
    _assert_sensor(picnic.hass, "sensor.picnic_cart_total_price", STATE_UNAVAILABLE)
    _assert_sensor(picnic.hass, "sensor.picnic_selected_slot_start", STATE_UNAVAILABLE)
    _assert_sensor(picnic.hass, "sensor.picnic_selected_slot_end", STATE_UNAVAILABLE)
    _assert_sensor(
        picnic.hass, "sensor.picnic_selected_slot_max_order_time", STATE_UNAVAILABLE
    )
    _assert_sensor(
        picnic.hass, "sensor.picnic_selected_slot_min_order_value", STATE_UNAVAILABLE
    )
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_eta_start", STATE_UNAVAILABLE)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_eta_end", STATE_UNAVAILABLE)
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_delivery_time", STATE_UNAVAILABLE
    )


async def test_sensors_malformed_delivery_data(picnic: PicnicTestData):
    """Test sensor states when the delivery api returns not a list."""
    # Setup platform with default responses
    await _setup_platform(picnic, use_default_responses=True)

    # Change mock responses to empty data and refresh the coordinator
    picnic.api_client.get_deliveries.return_value = {"error": "message"}
    await _get_coordinator(picnic).async_refresh()

    # Assert all last-order sensors have STATE_UNAVAILABLE because the delivery info fetch failed
    assert _get_coordinator(picnic).last_update_success is True
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_eta_start", STATE_UNAVAILABLE)
    _assert_sensor(picnic.hass, "sensor.picnic_last_order_eta_end", STATE_UNAVAILABLE)
    _assert_sensor(
        picnic.hass, "sensor.picnic_last_order_delivery_time", STATE_UNAVAILABLE
    )


async def test_sensors_malformed_response(picnic: PicnicTestData):
    """Test coordinator update fails when API yields ValueError."""
    # Setup platform with default responses
    await _setup_platform(picnic, use_default_responses=True)

    # Change mock responses to empty data and refresh the coordinator
    picnic.api_client.get_user.side_effect = ValueError
    picnic.api_client.get_cart.side_effect = ValueError
    await _get_coordinator(picnic).async_refresh()

    # Assert coordinator update failed
    assert _get_coordinator(picnic).last_update_success is False


async def test_device_registry_entry(picnic: PicnicTestData):
    """Test if device registry entry is populated correctly."""
    # Setup platform and default mock responses
    await _setup_platform(picnic, use_default_responses=True)

    device_registry = await picnic.hass.helpers.device_registry.async_get_registry()
    picnic_service = device_registry.async_get_device(
        identifiers={(const.DOMAIN, DEFAULT_USER_RESPONSE["user_id"])}
    )
    assert picnic_service.model == DEFAULT_USER_RESPONSE["user_id"]
    assert picnic_service.name == "Picnic: Commonstreet 123a"
    assert picnic_service.entry_type is DeviceEntryType.SERVICE


async def test_auth_token_is_saved_on_update(picnic: PicnicTestData):
    """Test that auth-token changes in the session object are reflected by the config entry."""
    # Setup platform and default mock responses
    await _setup_platform(picnic, use_default_responses=True)

    # Set a different auth token in the session mock
    updated_auth_token = "x-updated-picnic-auth-token"
    picnic.api_client.session.auth_token = updated_auth_token

    # Verify the updated auth token is not set and fetch data using the coordinator
    assert picnic.config_entry.data.get(CONF_ACCESS_TOKEN) != updated_auth_token
    await _get_coordinator(picnic).async_refresh()

    # Verify that the updated auth token is saved in the config entry
    assert picnic.config_entry.data.get(CONF_ACCESS_TOKEN) == updated_auth_token
