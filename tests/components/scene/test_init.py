"""The tests for the Scene component."""
import io

import pytest

from homeassistant.components import light, scene
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import loader as yaml_loader

from tests.common import async_mock_service


@pytest.fixture(autouse=True)
def entities(hass):
    """Initialize the test light."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    yield platform.ENTITIES[0:2]


async def test_config_yaml_alias_anchor(hass, entities):
    """Test the usage of YAML aliases and anchors.

    The following test scene configuration is equivalent to:

    scene:
      - name: test
        entities:
          light_1: &light_1_state
            state: 'on'
            brightness: 100
          light_2: *light_1_state

    When encountering a YAML alias/anchor, the PyYAML parser will use a
    reference to the original dictionary, instead of creating a copy, so
    care needs to be taken to not modify the original.
    """
    light_1, light_2 = await setup_lights(hass, entities)
    entity_state = {"state": "on", "brightness": 100}

    assert await async_setup_component(
        hass,
        scene.DOMAIN,
        {
            "scene": [
                {
                    "name": "test",
                    "entities": {
                        light_1.entity_id: entity_state,
                        light_2.entity_id: entity_state,
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await activate(hass, "scene.test")

    assert light.is_on(hass, light_1.entity_id)
    assert light.is_on(hass, light_2.entity_id)
    assert 100 == light_1.last_call("turn_on")[1].get("brightness")
    assert 100 == light_2.last_call("turn_on")[1].get("brightness")


async def test_config_yaml_bool(hass, entities):
    """Test parsing of booleans in yaml config."""
    light_1, light_2 = await setup_lights(hass, entities)

    config = (
        "scene:\n"
        "  - name: test\n"
        "    entities:\n"
        f"      {light_1.entity_id}: on\n"
        f"      {light_2.entity_id}:\n"
        "        state: on\n"
        "        brightness: 100\n"
    )

    with io.StringIO(config) as file:
        doc = yaml_loader.yaml.safe_load(file)

    assert await async_setup_component(hass, scene.DOMAIN, doc)
    await hass.async_block_till_done()

    await activate(hass, "scene.test")

    assert light.is_on(hass, light_1.entity_id)
    assert light.is_on(hass, light_2.entity_id)
    assert 100 == light_2.last_call("turn_on")[1].get("brightness")


async def test_activate_scene(hass, entities):
    """Test active scene."""
    light_1, light_2 = await setup_lights(hass, entities)

    assert await async_setup_component(
        hass,
        scene.DOMAIN,
        {
            "scene": [
                {
                    "name": "test",
                    "entities": {
                        light_1.entity_id: "on",
                        light_2.entity_id: {"state": "on", "brightness": 100},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await activate(hass, "scene.test")

    assert light.is_on(hass, light_1.entity_id)
    assert light.is_on(hass, light_2.entity_id)
    assert light_2.last_call("turn_on")[1].get("brightness") == 100

    calls = async_mock_service(hass, "light", "turn_on")

    await hass.services.async_call(
        scene.DOMAIN, "turn_on", {"transition": 42, "entity_id": "scene.test"}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == "light"
    assert calls[0].service == "turn_on"
    assert calls[0].data.get("transition") == 42


async def activate(hass, entity_id=ENTITY_MATCH_ALL):
    """Activate a scene."""
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(scene.DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def test_services_registered(hass):
    """Test we register services with empty config."""
    assert await async_setup_component(hass, "scene", {})
    assert hass.services.has_service("scene", "reload")
    assert hass.services.has_service("scene", "turn_on")
    assert hass.services.has_service("scene", "apply")


async def setup_lights(hass, entities):
    """Set up the light component."""
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {"platform": "test"}}
    )
    await hass.async_block_till_done()

    light_1, light_2 = entities

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [light_1.entity_id, light_2.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert not light.is_on(hass, light_1.entity_id)
    assert not light.is_on(hass, light_2.entity_id)

    return light_1, light_2
