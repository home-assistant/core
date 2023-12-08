"""Test openAQ component setup process."""

from unittest import mock

from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup, TestingOpenAQ

from tests.common import MockConfigEntry


@mock.patch("openaq.__new__", TestingOpenAQ("location_good.json"))
async def test_add_correct_devices(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities."""
    await setup_integration(config_entry)
    assert await async_setup_component(hass, DOMAIN, config_entry)
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 5


@mock.patch("openaq.__new__", TestingOpenAQ("location_bad.json"))
async def test_add_incorrect_devices(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities where one entity is inorrect."""
    await setup_integration(config_entry)
    assert await async_setup_component(hass, DOMAIN, config_entry)
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 5
