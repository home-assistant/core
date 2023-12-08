"""Test openAQ component setup process."""

from unittest import mock

import pytest

from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup, OpenAQMock

from tests.common import MockConfigEntry


@pytest.mark.asyncio
@mock.patch("openaq.__new__", OpenAQMock("location_good.json"))
async def test_add_correct_devices(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities."""
    await setup_integration(config_entry, "location_good.json")
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 5


@pytest.mark.asyncio
@mock.patch("openaq.__new__", OpenAQMock("location_bad.json"))
async def test_add_correct_and_incorrect_devices(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities where one entity is inorrect."""
    await setup_integration(config_entry, "location_bad.json")
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 5


@pytest.mark.asyncio
@mock.patch("openaq.__new__", OpenAQMock("location_no_devices.json"))
async def test_no_devices(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities where one entity is inorrect."""
    await setup_integration(config_entry, "location_no_devices.json")
    assert await async_setup_component(hass, DOMAIN, config_entry)
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 1  # only last_updated should be here


@pytest.mark.asyncio
@mock.patch("openaq.__new__", OpenAQMock("location_wrong_location_id.json"))
async def test_wrong_location_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test for successfully setting up the platform and entities where one entity is inorrect."""
    await setup_integration(config_entry, "location_wrong_location_id.json")
    assert await async_setup_component(hass, DOMAIN, config_entry)
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 0
