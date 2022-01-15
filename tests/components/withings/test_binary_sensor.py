"""Tests for the Withings component."""
from withings_api.common import NotifyAppli

from homeassistant.components.withings.common import (
    WITHINGS_MEASUREMENTS_MAP,
    async_get_entity_id,
)
from homeassistant.components.withings.const import Measurement
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import ComponentFactory, new_profile_config


async def test_binary_sensor(
    hass: HomeAssistant, component_factory: ComponentFactory, current_request_with_host
) -> None:
    """Test binary sensor."""
    in_bed_attribute = WITHINGS_MEASUREMENTS_MAP[Measurement.IN_BED]
    person0 = new_profile_config("person0", 0)
    person1 = new_profile_config("person1", 1)

    entity_registry: EntityRegistry = er.async_get(hass)

    await component_factory.configure_component(profile_configs=(person0, person1))
    assert not await async_get_entity_id(hass, in_bed_attribute, person0.user_id)
    assert not await async_get_entity_id(hass, in_bed_attribute, person1.user_id)

    # person 0
    await component_factory.setup_profile(person0.user_id)
    await component_factory.setup_profile(person1.user_id)

    entity_id0 = await async_get_entity_id(hass, in_bed_attribute, person0.user_id)
    entity_id1 = await async_get_entity_id(hass, in_bed_attribute, person1.user_id)
    assert entity_id0
    assert entity_id1

    assert entity_registry.async_is_registered(entity_id0)
    assert hass.states.get(entity_id0).state == STATE_UNAVAILABLE

    resp = await component_factory.call_webhook(person0.user_id, NotifyAppli.BED_IN)
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id0).state == STATE_ON

    resp = await component_factory.call_webhook(person0.user_id, NotifyAppli.BED_OUT)
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id0).state == STATE_OFF

    # person 1
    assert hass.states.get(entity_id1).state == STATE_UNAVAILABLE

    resp = await component_factory.call_webhook(person1.user_id, NotifyAppli.BED_IN)
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id1).state == STATE_ON

    # Unload
    await component_factory.unload(person0)
    await component_factory.unload(person1)
