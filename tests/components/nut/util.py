"""Tests for the nut integration."""

import json
from unittest.mock import MagicMock, patch

from spencerassistant.components.nut.const import DOMAIN
from spencerassistant.const import CONF_HOST, CONF_PORT
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry, load_fixture


def _get_mock_pynutclient(list_vars=None, list_ups=None):
    pynutclient = MagicMock()
    type(pynutclient).list_ups = MagicMock(return_value=list_ups)
    type(pynutclient).list_vars = MagicMock(return_value=list_vars)
    return pynutclient


async def async_init_integration(
    hass: spencerAssistant, ups_fixture: str
) -> MockConfigEntry:
    """Set up the nexia integration in spencer Assistant."""

    ups_fixture = f"nut/{ups_fixture}.json"
    list_vars = json.loads(load_fixture(ups_fixture))

    mock_pynut = _get_mock_pynutclient(list_ups={"ups1": "UPS 1"}, list_vars=list_vars)

    with patch(
        "spencerassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "mock", CONF_PORT: "mock"},
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
