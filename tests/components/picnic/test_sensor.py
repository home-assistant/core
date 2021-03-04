"""The tests for the Picnic sensor platform."""
import copy
import unittest
from unittest.mock import patch

from homeassistant.components.picnic import const
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL
from homeassistant.const import STATE_UNAVAILABLE, CURRENCY_EURO, DEVICE_CLASS_TIMESTAMP
from tests.common import MockConfigEntry, async_test_home_assistant

DEFAULT_USER_RESPONSE = {
    "user_id": "295-6y3-1nf4",
    "firstname": "User",
    "lastname": "Name",
    "address": {
        "house_number": 123,
        "house_number_ext": "a",
        "postcode": "4321 AB",
        "street": "Commonstreet",
        "city": "Somewhere"
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
            "minimum_order_value": 3500
        },
    ],
    "selected_slot": {
        "slot_id": "611a3b074872b23576bef456a",
        "state": "EXPLICIT"
    },
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
        "end": "2021-02-26T21:14:00.000+01:00"
    },
    "status": "COMPLETED",
    "delivery_time": {
        "start": "2021-02-26T20:54:05.221+01:00",
        "end": "2021-02-26T20:58:31.802+01:00"
    },
    "orders": [
        {
            "creation_time": "2021-02-24T21:48:46.418+01:00",
            "total_price": 3597,
        },
        {
            "creation_time": "2021-02-25T17:10:26.816+01:00",
            "total_price": 536,
        }
    ]
}


class TestPicnicSensor(unittest.IsolatedAsyncioTestCase):
    """Test the Picnic sensor."""

    async def asyncSetUp(self):
        """Set up things to be run when tests are started."""
        self.hass = await async_test_home_assistant(None)

        # Patch the api client
        self.picnic_patcher = patch("homeassistant.components.picnic.PicnicAPI")
        self.picnic_mock = self.picnic_patcher.start()

        # Add a config entry and setup the integration
        config_data = {
            "username": "test-user",
            "password": "pass",
            "country_code": "NL",
        }
        self.config_entry = MockConfigEntry(
            domain=const.DOMAIN,
            data=config_data,
            connection_class=CONN_CLASS_CLOUD_POLL,
            unique_id="295-6y3-1nf4",
        )
        self.config_entry.add_to_hass(self.hass)

        await self.hass.config_entries.async_setup(self.config_entry.entry_id)
        await self.hass.async_block_till_done()

        self.coordinator = self.hass.data[const.DOMAIN][self.config_entry.entry_id][const.CONF_COORDINATOR]

    async def asyncTearDown(self):
        """Tear down the test setup, stop patchers."""
        await self.hass.async_stop()
        self.picnic_patcher.stop()

    def _assert_sensor(self, name, state, cls=None, unit=None):
        sensor = self.hass.states.get(name)
        assert sensor.state == state
        if cls:
            assert sensor.attributes["device_class"] == cls
        if unit:
            assert sensor.attributes["unit_of_measurement"] == unit

    async def test_sensors_setup(self):
        """Test the default sensor setup behaviour."""
        self.picnic_mock().get_user.return_value = DEFAULT_USER_RESPONSE
        self.picnic_mock().get_cart.return_value = DEFAULT_CART_RESPONSE
        self.picnic_mock().get_deliveries.return_value = [DEFAULT_DELIVERY_RESPONSE]
        await self.coordinator.async_refresh()

        self._assert_sensor("sensor.picnic_completed_deliveries", "112")
        self._assert_sensor("sensor.picnic_total_deliveries", "123")
        self._assert_sensor("sensor.picnic_cart_items_count", "10")
        self._assert_sensor("sensor.picnic_cart_total_price", "25.35",
                            unit=CURRENCY_EURO)
        self._assert_sensor("sensor.picnic_selected_slot_start", "2021-03-03T14:45:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_selected_slot_end", "2021-03-03T15:45:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_selected_slot_max_order_time", "2021-03-02T22:00:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_selected_slot_min_order_value", "35.0")
        self._assert_sensor("sensor.picnic_last_order_slot_start", "2021-02-26T20:15:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_last_order_slot_end", "2021-02-26T21:15:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_last_order_status", "COMPLETED")
        self._assert_sensor("sensor.picnic_last_order_eta_start", "2021-02-26T20:54:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_last_order_eta_end", "2021-02-26T21:14:00.000+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_last_order_delivery_time", "2021-02-26T20:54:05.221+01:00",
                            cls=DEVICE_CLASS_TIMESTAMP)
        self._assert_sensor("sensor.picnic_last_order_total_price", "41.33",
                            unit=CURRENCY_EURO)

    async def test_sensors_no_selected_time_slot(self):
        """Test sensor states with no explicit selected time slot."""
        # Adjust cart response
        cart_response = copy.deepcopy(DEFAULT_CART_RESPONSE)
        cart_response["selected_slot"]["state"] = "IMPLICIT"

        # Set mock responses
        self.picnic_mock().get_user.return_value = DEFAULT_USER_RESPONSE
        self.picnic_mock().get_cart.return_value = cart_response
        self.picnic_mock().get_deliveries.return_value = [DEFAULT_DELIVERY_RESPONSE]
        await self.coordinator.async_refresh()

        # Assert sensors are unavailable
        self._assert_sensor("sensor.picnic_selected_slot_start", STATE_UNAVAILABLE)
        self._assert_sensor("sensor.picnic_selected_slot_end", STATE_UNAVAILABLE)
        self._assert_sensor("sensor.picnic_selected_slot_max_order_time", STATE_UNAVAILABLE)
        self._assert_sensor("sensor.picnic_selected_slot_min_order_value", STATE_UNAVAILABLE)

    async def test_sensors_last_order_in_future(self):
        """Test sensor states when last order is not yet delivered."""
        # Adjust default delivery response
        delivery_response = copy.deepcopy(DEFAULT_DELIVERY_RESPONSE)
        del delivery_response["delivery_time"]

        # Set mock responses
        self.picnic_mock().get_user.return_value = DEFAULT_USER_RESPONSE
        self.picnic_mock().get_cart.return_value = DEFAULT_CART_RESPONSE
        self.picnic_mock().get_deliveries.return_value = [delivery_response]
        await self.coordinator.async_refresh()

        # Assert delivery time is not available, but eta is
        self._assert_sensor("sensor.picnic_last_order_delivery_time", STATE_UNAVAILABLE)
        self._assert_sensor("sensor.picnic_last_order_eta_start", "2021-02-26T20:54:00.000+01:00")
        self._assert_sensor("sensor.picnic_last_order_eta_end", "2021-02-26T21:14:00.000+01:00")
