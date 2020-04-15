"""Tests for the nut integration."""

import json

from asynctest import MagicMock, patch

from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import CONF_ALIAS, CONF_HOST, CONF_PORT, CONF_RESOURCES
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def _get_mock_pynutclient(list_vars=None, list_ups=None):
    pynutclient = MagicMock()
    type(pynutclient).list_ups = MagicMock(return_value=list_ups)
    type(pynutclient).list_vars = MagicMock(return_value=list_vars)
    return pynutclient


async def async_init_integration(
    hass: HomeAssistant, host: str, ups_fixture: str, resources: list, mac_addr: str
) -> MockConfigEntry:
    """Set up the nexia integration in Home Assistant."""

    fixture_path = f"nut/{ups_fixture}.json"
    list_vars = json.loads(load_fixture(fixture_path))

    mock_pynut = _get_mock_pynutclient(list_ups={"ups1": "UPS 1"}, list_vars=list_vars)

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut
    ), patch("getmac.get_mac_address", return_value=mac_addr):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: host,
                CONF_PORT: "mock",
                CONF_ALIAS: "ups1",
                CONF_RESOURCES: resources,
            },
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
