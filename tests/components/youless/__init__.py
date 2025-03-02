"""Tests for the youless component."""

import requests_mock

from homeassistant.components import youless
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


async def init_component(hass: HomeAssistant) -> MockConfigEntry:
    """Check if the setup of the integration succeeds."""
    with requests_mock.Mocker() as mock:
        mock.get(
            "http://1.1.1.1/d",
            json=load_json_object_fixture("device.json", youless.DOMAIN),
        )
        mock.get(
            "http://1.1.1.1/e",
            json=load_json_array_fixture("enologic.json", youless.DOMAIN),
            headers={"Content-Type": "application/json"},
        )
        mock.get(
            "http://1.1.1.1/f",
            json=load_json_object_fixture("phase.json", youless.DOMAIN),
            headers={"Content-Type": "application/json"},
        )

        entry = MockConfigEntry(
            domain=youless.DOMAIN,
            title="localhost",
            data={CONF_HOST: "1.1.1.1", CONF_DEVICE: "localhost"},
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
