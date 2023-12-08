from unittest import mock

from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup, TestingOpenAQ

from tests.common import MockConfigEntry


@mock.patch("openaq.__new__", TestingOpenAQ)
async def test_hello_incorrect(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    await setup_integration(config_entry)
    assert await async_setup_component(hass, DOMAIN, config_entry)
    state = hass.states.get("sensor.openAQ")
    hass.config_entries.async_entries(DOMAIN)[0]

    assert state == 1515
