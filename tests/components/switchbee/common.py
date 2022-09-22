"""Common methods used across the tests for switchbee devices."""
import json
from unittest.mock import patch

from homeassistant.components.switchbee import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    ).add_to_hass(hass)

    coordinator_data = json.loads(load_fixture("switchbee.json", "switchbee"))
    fetch_states_data = json.loads(load_fixture("switchbee_states.json", "switchbee"))

    with patch("homeassistant.components.switchbee.PLATFORMS", [platform]), patch(
        "switchbee.api.CentralUnitAPI.get_configuration",
        return_value=coordinator_data,
    ), patch(
        "switchbee.api.CentralUnitAPI.get_multiple_states",
        return_value=fetch_states_data,
    ), patch(
        "switchbee.api.CentralUnitAPI._login", return_value=None
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
