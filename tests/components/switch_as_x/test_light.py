"""Tests for the Switch as X Light platform."""
import pytest

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    COLOR_MODE_ONOFF,
)
from homeassistant.components.switch_as_x import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.light import common
from tests.components.switch import common as switch_common


async def test_default_state(hass):
    """Test light switch default state."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": "switch.test", "target_domain": "light"},
        title="Christmas Tree Lights",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.christmas_tree_lights")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["supported_features"] == 0
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [COLOR_MODE_ONOFF]
    assert state.attributes.get(ATTR_COLOR_MODE) is None


async def test_light_service_calls(hass):
    """Test service calls to light."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": "switch.decorative_lights", "target_domain": "light"},
        title="decorative_lights",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.decorative_lights").state == "on"

    await common.async_toggle(hass, "light.decorative_lights")

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.decorative_lights").state == "off"

    await common.async_turn_on(hass, "light.decorative_lights")

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.decorative_lights").state == "on"
    assert (
        hass.states.get("light.decorative_lights").attributes.get(ATTR_COLOR_MODE)
        == COLOR_MODE_ONOFF
    )

    await common.async_turn_off(hass, "light.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.decorative_lights").state == "off"


async def test_switch_service_calls(hass):
    """Test service calls to switch."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": "switch.decorative_lights", "target_domain": "light"},
        title="decorative_lights",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.decorative_lights").state == "on"

    await switch_common.async_turn_off(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.decorative_lights").state == "off"

    await switch_common.async_turn_on(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.decorative_lights").state == "on"


@pytest.mark.parametrize("target_domain", ("light",))
async def test_config_entry_entity_id(hass: HomeAssistant, target_domain):
    """Test light switch setup from config entry with entity id."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": "switch.abc", "target_domain": target_domain},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.config.components

    state = hass.states.get(f"{target_domain}.abc")
    assert state.state == "unavailable"
    # Name copied from config entry title
    assert state.name == "ABC"

    # Check the light is added to the entity registry
    registry = er.async_get(hass)
    entity_entry = registry.async_get(f"{target_domain}.abc")
    assert entity_entry.unique_id == config_entry.entry_id


@pytest.mark.parametrize("target_domain", ("light",))
async def test_config_entry_uuid(hass: HomeAssistant, target_domain):
    """Test light switch setup from config entry with entity registry id."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": registry_entry.id, "target_domain": target_domain},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{target_domain}.abc")


@pytest.mark.parametrize("target_domain", ("light",))
async def test_device(hass: HomeAssistant, target_domain):
    """Test the entity is added to the wrapped entity's device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    test_config_entry = MockConfigEntry()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=test_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", device_id=device_entry.id
    )

    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": switch_entity_entry.id, "target_domain": target_domain},
        title="ABC",
    )

    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(f"{target_domain}.abc")
    assert entity_entry.device_id == switch_entity_entry.device_id
