"""The tests for the Light Switch platform."""

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    COLOR_MODE_ONOFF,
)
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.light import common
from tests.components.switch import common as switch_common


async def test_default_state(hass):
    """Test light switch default state."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "switch",
                "entity_id": "switch.test",
                "name": "Christmas Tree Lights",
            }
        },
    )
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
    await async_setup_component(
        hass,
        "light",
        {"light": [{"platform": "switch", "entity_id": "switch.decorative_lights"}]},
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_switch").state == "on"

    await common.async_toggle(hass, "light.light_switch")

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"

    await common.async_turn_on(hass, "light.light_switch")

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.light_switch").state == "on"
    assert (
        hass.states.get("light.light_switch").attributes.get(ATTR_COLOR_MODE)
        == COLOR_MODE_ONOFF
    )

    await common.async_turn_off(hass, "light.light_switch")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"


async def test_switch_service_calls(hass):
    """Test service calls to switch."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await async_setup_component(
        hass,
        "light",
        {"light": [{"platform": "switch", "entity_id": "switch.decorative_lights"}]},
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_switch").state == "on"

    await switch_common.async_turn_off(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"

    await switch_common.async_turn_on(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.light_switch").state == "on"


async def test_config_entry(hass: HomeAssistant):
    """Test light switch setup from config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=SWITCH_DOMAIN,
        options={"entity_id": "switch.abc"},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert SWITCH_DOMAIN in hass.config.components

    state = hass.states.get("light.abc")
    assert state.state == "unavailable"
    # Name copied from config entry title
    assert state.name == "ABC"

    # Check the light is added to the entity registry
    registry = er.async_get(hass)
    entity_entry = registry.async_get("light.abc")
    assert entity_entry.unique_id == config_entry.entry_id


async def test_config_entry_uuid(hass: HomeAssistant):
    """Test light switch setup from config entry with entity registry id."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")

    config_entry = MockConfigEntry(
        data={},
        domain=SWITCH_DOMAIN,
        options={"entity_id": registry_entry.id},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.abc")


async def test_config_entry_unregistered_uuid(hass: HomeAssistant):
    """Test light switch setup from config entry with unknown entity registry id."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"

    config_entry = MockConfigEntry(
        data={},
        domain=SWITCH_DOMAIN,
        options={"entity_id": fake_uuid},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_light_switch_hack(hass: HomeAssistant, enable_custom_integrations):
    """Test light switch hack."""
    platform = getattr(hass.components, "test.switch")
    platform.init(empty=True)
    platform.ENTITIES.append(platform.MockToggleEntity("AC", "on", "unique"))

    registry = er.async_get(hass)
    switch_registry_entry = registry.async_get_or_create(
        "switch",
        "test",
        "unique",
    )
    registry.async_update_entity_options(
        switch_registry_entry.entity_id, "switch", {"component": "light"}
    )

    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "test",
            },
        },
    )
    await hass.async_block_till_done()

    # No switch state
    assert not hass.states.async_all("switch")

    # A light state
    lights = hass.states.async_all("light")
    assert len(lights) == 1

    # The light has its own entity registry entry
    light_registry_entry = registry.async_get(lights[0].entity_id)
    assert light_registry_entry != switch_registry_entry
