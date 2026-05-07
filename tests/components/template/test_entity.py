"""Test abstract template entity."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.template import entity as abstract_entity
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_template_entity_not_implemented(hass: HomeAssistant) -> None:
    """Test abstract template entity raises not implemented error."""

    with pytest.raises(TypeError):
        _ = abstract_entity.AbstractTemplateEntity(hass, {})


@pytest.mark.parametrize(
    "config",
    [
        # State-based template light
        {
            "template": {
                "light": {
                    "name": "test_light",
                    "state": "{{ true }}",
                    "turn_on": [
                        {"delay": {"seconds": 120}},
                    ],
                    "turn_off": {"event": "turn_off"},
                },
            }
        },
        # Trigger-based template light
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "light": {
                    "name": "test_light",
                    "state": "{{ true }}",
                    "turn_on": [
                        {"delay": {"seconds": 120}},
                    ],
                    "turn_off": {"event": "turn_off"},
                },
            }
        },
    ],
    ids=["state_based", "trigger_based"],
)
async def test_reload_stops_entity_action_scripts(
    hass: HomeAssistant, config: dict
) -> None:
    """Test that reloading stops template entity action scripts."""
    assert await async_setup_component(hass, "template", config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    entity = hass.data["light"].get_entity("light.test_light")
    assert entity is not None

    # Call turn_on — script will start and hang on delay
    hass.async_create_task(
        hass.services.async_call("light", "turn_on", {"entity_id": "light.test_light"})
    )
    await asyncio.sleep(0)

    turn_on_script = entity._action_scripts["turn_on"]
    assert turn_on_script.is_running

    # Reload with empty config removes the entity and stops scripts
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"template": []},
    ):
        await hass.services.async_call("template", SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    assert not turn_on_script.is_running
    assert turn_on_script._unloaded
    assert hass.data["light"].get_entity("light.test_light") is None
