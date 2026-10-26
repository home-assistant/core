"""Test abstract template entity."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.cover import CoverState
from homeassistant.components.light import ColorMode
from homeassistant.components.template import DOMAIN, entity as abstract_entity
from homeassistant.const import SERVICE_RELOAD, STATE_ON, STATE_UNAVAILABLE
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


_BASE_CONFIGS: dict[str, dict] = {
    "cover": {"open_cover": [], "close_cover": []},
    "climate": {
        "hvac_mode": "{{ 'heat' }}",
        "hvac_modes": "{{ ['off', 'heat'] }}",
        "set_hvac_mode": [],
    },
    "device_tracker": {"latitude": "{{ 10 }}", "longitude": "{{ 20 }}"},
    "fan": {
        "state": "{{ true }}",
        "turn_on": [],
        "turn_off": [],
        "percentage": "{{ 50 }}",
        "set_percentage": [],
    },
    "light": {"state": "{{ true }}", "turn_on": [], "turn_off": []},
    "sensor": {},
    "vacuum": {
        "state": "{{ 'docked' }}",
        "start": [],
        "fan_speeds": ["low", "high"],
        "set_fan_speed": [],
    },
    "lock": {"state": "{{ 'locked' }}", "lock": [], "unlock": []},
    "weather": {
        "condition": "{{ 'sunny' }}",
        "humidity": "{{ 50 }}",
        "temperature": "{{ 20 }}",
    },
}


def _config(domain: str, **extra_config: str | list) -> dict:
    return {
        "template": {
            domain: {
                "unique_id": "unique_1",
                "default_entity_id": f"{domain}.test",
                **_BASE_CONFIGS[domain],
                **extra_config,
            }
        }
    }


@pytest.mark.parametrize(
    "apply_config",
    [pytest.param(_reload, id="reload"), pytest.param(_restart, id="restart")],
)
@pytest.mark.parametrize(
    ("old_config", "new_config", "entity_id", "expected_attributes"),
    [
        pytest.param(
            _config("light", name="Old name"),
            _config("light", name="New name", set_level=[]),
            "light.test",
            {
                "friendly_name": "New name",
                "supported_color_modes": [ColorMode.BRIGHTNESS],
                "color_mode": ColorMode.BRIGHTNESS,
            },
            id="light_name_and_color_modes",
        ),
        pytest.param(
            _config(
                "light",
                temperature="{{ 300 }}",
                set_temperature=[],
                min_mireds="{{ 200 }}",
            ),
            _config("light", temperature="{{ 300 }}", set_temperature=[]),
            "light.test",
            {"max_color_temp_kelvin": 6535},
            id="light_color_temp_range",
        ),
        pytest.param(
            _config(
                "light",
                temperature="{{ 300 }}",
                set_temperature=[],
                min_mireds="{{ 200 }}",
            ),
            _config(
                "light",
                temperature="{{ 160 }}",
                set_temperature=[],
                min_mireds="{{ 153 }}",
            ),
            "light.test",
            {"max_color_temp_kelvin": 6535, "color_temp_kelvin": 6250},
            id="light_color_temp_and_range",
        ),
        pytest.param(
            _config(
                "light",
                level="{{ 250 }}",
                set_level=[],
                temperature="{{ 250 }}",
                set_temperature=[],
                min_mireds="{{ 250 }}",
            ),
            _config(
                "light",
                level="{{ 200 }}",
                set_level=[],
                temperature="{{ 200 }}",
                set_temperature=[],
                min_mireds="{{ 153 }}",
            ),
            "light.test",
            {"color_temp_kelvin": 5000},
            id="light_shared_temperature_template",
        ),
        pytest.param(
            _config(
                "light",
                temperature="{{ 500 }}",
                set_temperature=[],
                min_mireds="{{ 400 }}",
                max_mireds="{{ 600 }}",
            ),
            _config(
                "light",
                temperature="{{ 300 }}",
                set_temperature=[],
                min_mireds="{{ 200 }}",
                max_mireds="{{ 300 }}",
            ),
            "light.test",
            {"color_temp_kelvin": 3333},
            id="light_temperature_shared_with_bound",
        ),
        pytest.param(
            _config(
                "light",
                level="{{ 100 }}",
                set_level=[],
                rgb="{{ (255, 0, 0) }}",
                set_rgb=[],
            ),
            _config("light", rgb="{{ (255, 0, 0) }}", set_rgb=[]),
            "light.test",
            {"color_mode": ColorMode.RGB, "brightness": None},
            id="light_brightness",
        ),
        pytest.param(
            _config(
                "climate", current_temperature="{{ 21 }}", current_humidity="{{ 40 }}"
            ),
            _config("climate"),
            "climate.test",
            {"current_temperature": None, "current_humidity": None},
            id="climate_measurements",
        ),
        pytest.param(
            _config("climate", hvac_action="{{ 'heating' }}"),
            _config("climate"),
            "climate.test",
            {"hvac_action": None},
            id="climate_hvac_action",
        ),
        pytest.param(
            _config("device_tracker", location_accuracy="{{ 5 }}"),
            _config("device_tracker"),
            "device_tracker.test",
            {"gps_accuracy": 0},
            id="device_tracker_location_accuracy",
        ),
        pytest.param(
            _config("lock", code_format="{{ '\\\\d+' }}"),
            _config("lock"),
            "lock.test",
            {"code_format": None},
            id="lock_code_format",
        ),
        pytest.param(
            _config(
                "fan",
                preset_mode="{{ 'auto' }}",
                preset_modes=["auto"],
                set_preset_mode=[],
            ),
            _config("fan"),
            "fan.test",
            {"percentage": 50, "preset_mode": None},
            id="fan_preset_mode",
        ),
        pytest.param(
            _config("vacuum", fan_speed="{{ 'low' }}"),
            _config("vacuum"),
            "vacuum.test",
            {"fan_speed": None},
            id="vacuum_fan_speed",
        ),
        pytest.param(
            _config("weather", ozone="{{ 5 }}", wind_bearing="{{ 180 }}"),
            _config("weather"),
            "weather.test",
            {"ozone": None, "wind_bearing": None},
            id="weather_measurements",
        ),
    ],
)
async def test_values_without_template_not_restored(
    hass: HomeAssistant,
    apply_config: Callable[[HomeAssistant, dict], Awaitable[None]],
    old_config: dict,
    new_config: dict,
    entity_id: str,
    expected_attributes: dict,
) -> None:
    """Test values that only came from the old configuration are not restored."""
    assert await async_setup_component(hass, DOMAIN, old_config)
    await hass.async_block_till_done()

    await apply_config(hass, new_config)

    state = hass.states.get(entity_id)
    for attribute, value in expected_attributes.items():
        assert state.attributes.get(attribute) == value


@pytest.mark.parametrize(
    "apply_config",
    [pytest.param(_reload, id="reload"), pytest.param(_restart, id="restart")],
)
async def test_this_state_is_restored_state(
    hass: HomeAssistant,
    apply_config: Callable[[HomeAssistant, dict], Awaitable[None]],
) -> None:
    """Test `this` refers to the restored state on the first render."""
    config = _config(
        "sensor",
        state=(
            "{{ states('sensor.source') if has_value('sensor.source')"
            " else this.state }}"
        ),
    )
    hass.states.async_set("sensor.source", "42")
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test").state == "42"

    hass.states.async_set("sensor.source", STATE_UNAVAILABLE)
    await apply_config(hass, config)

    assert hass.states.get("sensor.test").state == "42"


@pytest.mark.parametrize(
    "apply_config",
    [pytest.param(_reload, id="reload"), pytest.param(_restart, id="restart")],
)
@pytest.mark.parametrize(
    ("new_config", "expected_state"),
    [
        pytest.param(
            {"state": "{{ 42 }}", "unit_of_measurement": "%"}, "42", id="numeric"
        ),
        pytest.param(
            {
                "state": "{{ '2026-01-01T00:00:00+00:00' }}",
                "device_class": "timestamp",
            },
            "2026-01-01T00:00:00+00:00",
            id="timestamp",
        ),
    ],
)
async def test_sensor_incompatible_restored_value(
    hass: HomeAssistant,
    apply_config: Callable[[HomeAssistant, dict], Awaitable[None]],
    new_config: dict,
    expected_state: str,
) -> None:
    """Test a restored value that does not fit the new configuration is dropped."""
    assert await async_setup_component(
        hass, DOMAIN, _config("sensor", state="{{ 'offline' }}")
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test").state == "offline"

    await apply_config(hass, _config("sensor", **new_config))

    assert hass.states.get("sensor.test").state == expected_state


@pytest.mark.parametrize(
    "apply_config",
    [pytest.param(_reload, id="reload"), pytest.param(_restart, id="restart")],
)
async def test_cover_motion_not_restored_without_state_template(
    hass: HomeAssistant,
    apply_config: Callable[[HomeAssistant, dict], Awaitable[None]],
) -> None:
    """Test the cover motion is not restored when no state template updates it."""
    assert await async_setup_component(
        hass, DOMAIN, _config("cover", state="{{ 'opening' }}")
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.test").state == CoverState.OPENING

    await apply_config(hass, _config("cover", position="{{ 100 }}"))

    assert hass.states.get("cover.test").state == CoverState.OPEN
