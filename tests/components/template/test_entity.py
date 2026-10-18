"""Test abstract template entity."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.light import ColorMode
from homeassistant.components.template import DOMAIN, entity as abstract_entity
from homeassistant.const import SERVICE_RELOAD, STATE_ON
from homeassistant.core import CoreState, HomeAssistant
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
    assert await async_setup_component(hass, DOMAIN, config)
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
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    assert not turn_on_script.is_running
    assert turn_on_script._unloaded
    assert hass.data["light"].get_entity("light.test_light") is None


async def test_reload_rendered_value_not_replaced_by_restored_value(
    hass: HomeAssistant,
) -> None:
    """Test templates rendered on reload are not replaced by the restored state."""

    def make_config(brightness: int) -> dict:
        return {
            "template": {
                "light": {
                    "name": "test_light",
                    "level": f"{{{{ {brightness} }}}}",
                    "turn_on": [],
                    "turn_off": [],
                    "set_level": [],
                }
            }
        }

    assert await async_setup_component(hass, DOMAIN, make_config(102))
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.test_light"}, blocking=True
    )
    state = hass.states.get("light.test_light")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 102

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=make_config(153),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    # The optimistic state is restored, the template result is kept
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 153


async def _reload(hass: HomeAssistant, config: dict) -> None:
    """Reload the template integration with a new configuration."""
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()


async def _restart(hass: HomeAssistant, config: dict) -> None:
    """Re-add the entities with a new configuration while starting up."""
    hass.set_state(CoreState.not_running)
    await _reload(hass, config)
    await hass.async_start()
    await hass.async_block_till_done()


def _light_config(**extra_config: str | list) -> dict:
    return {
        "template": {
            "light": {
                "unique_id": "light_1",
                "default_entity_id": "light.test_light",
                "state": "{{ true }}",
                "turn_on": [],
                "turn_off": [],
                **extra_config,
            }
        }
    }


@pytest.mark.parametrize(
    "apply_config",
    [pytest.param(_reload, id="reload"), pytest.param(_restart, id="restart")],
)
@pytest.mark.parametrize(
    ("old_config", "new_config", "expected_attributes"),
    [
        pytest.param(
            _light_config(name="Old name"),
            _light_config(name="New name", set_level=[]),
            {
                "friendly_name": "New name",
                "supported_color_modes": [ColorMode.BRIGHTNESS],
                "color_mode": ColorMode.BRIGHTNESS,
            },
            id="name_and_color_modes",
        ),
        pytest.param(
            _light_config(
                temperature="{{ 300 }}",
                set_temperature=[],
                min_mireds="{{ 200 }}",
            ),
            _light_config(temperature="{{ 300 }}", set_temperature=[]),
            {"max_color_temp_kelvin": 6535},
            id="color_temp_range",
        ),
        pytest.param(
            _light_config(
                temperature="{{ 300 }}",
                set_temperature=[],
                min_mireds="{{ 200 }}",
            ),
            _light_config(
                temperature="{{ 160 }}",
                set_temperature=[],
                min_mireds="{{ 153 }}",
            ),
            {"max_color_temp_kelvin": 6535, "color_temp_kelvin": 6250},
            id="color_temp_and_range",
        ),
    ],
)
async def test_config_derived_values_not_restored(
    hass: HomeAssistant,
    apply_config: Callable[[HomeAssistant, dict], Awaitable[None]],
    old_config: dict,
    new_config: dict,
    expected_attributes: dict,
) -> None:
    """Test values derived from the configuration are not restored."""
    assert await async_setup_component(hass, DOMAIN, old_config)
    await hass.async_block_till_done()

    await apply_config(hass, new_config)

    state = hass.states.get("light.test_light")
    assert state.state == STATE_ON
    for attribute, value in expected_attributes.items():
        assert state.attributes[attribute] == value
