"""Tests for Picnic Tasks todo platform."""


import copy
import json
import unittest
from unittest.mock import patch

import pytest

from homeassistant.components.picnic import const
from homeassistant.components.picnic.const import CONF_COUNTRY_CODE
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_test_home_assistant, load_fixture

CART_FULL_RESPONSE = json.loads(load_fixture("picnic/cart.json"))
CART_NO_RESPONSE = {}
CART_EMPTY_RESPONSE = {
    "items": [],
}


@pytest.mark.usefixtures("hass_storage")
class TestPicnicSensor(unittest.IsolatedAsyncioTestCase):
    """Test the Picnic sensor."""

    async def asyncSetUp(self):
        """Set up things to be run when tests are started."""
        self.hass = await async_test_home_assistant(None)
        self.entity_registry = er.async_get(self.hass)

        # Patch the api client
        self.picnic_patcher = patch("homeassistant.components.picnic.PicnicAPI")
        self.picnic_mock = self.picnic_patcher.start()
        self.picnic_mock().session.auth_token = "3q29fpwhulzes"

        # Add a config entry and setup the integration
        config_data = {
            CONF_ACCESS_TOKEN: "x-original-picnic-auth-token",
            CONF_COUNTRY_CODE: "NL",
        }
        self.config_entry = MockConfigEntry(
            domain=const.DOMAIN,
            data=config_data,
            unique_id="295-6y3-1nf4",
        )
        self.config_entry.add_to_hass(self.hass)

    async def asyncTearDown(self):
        """Tear down the test setup, stop hass/patchers."""
        await self.hass.async_stop(force=True)
        self.picnic_patcher.stop()

    @property
    def _coordinator(self):
        return self.hass.data[const.DOMAIN][self.config_entry.entry_id][
            const.CONF_COORDINATOR
        ]

    async def _setup_platform(self, response):
        """Set up the Picnic sensor platform."""
        self.picnic_mock().get_cart.return_value = copy.deepcopy(response)

        await self.hass.config_entries.async_setup(self.config_entry.entry_id)
        await self.hass.async_block_till_done()

    async def test_cart_list_with_items(self):
        """Test loading of shopping cart."""
        await self._setup_platform(CART_FULL_RESPONSE)

        state = self.hass.states.get("todo.mock_title_shopping_cart")
        assert state
        assert state.state == "10"

    async def test_cart_list_empty_items(self):
        """Test loading of shopping cart."""
        await self._setup_platform(CART_EMPTY_RESPONSE)

        state = self.hass.states.get("todo.mock_title_shopping_cart")
        assert state
        assert state.state == "0"

    async def test_cart_list_no_response(self):
        """Test loading of shopping cart."""
        await self._setup_platform(CART_NO_RESPONSE)

        state = self.hass.states.get("todo.mock_title_shopping_cart")
        assert state is None
