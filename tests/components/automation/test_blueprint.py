"""Test built-in blueprints."""
import asyncio
import contextlib
from datetime import timedelta
import pathlib

from homeassistant.components import automation
from homeassistant.components.blueprint import models
from homeassistant.core import callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, yaml

from tests.async_mock import patch
from tests.common import async_fire_time_changed, async_mock_service

BUILTIN_BLUEPRINT_FOLDER = pathlib.Path(automation.__file__).parent / "blueprints"


@contextlib.contextmanager
def patch_blueprint(blueprint_path: str, data_path):
    """Patch blueprint loading from a different source."""
    orig_load = models.DomainBlueprints._load_blueprint

    @callback
    def mock_load_blueprint(self, path):
        if path != blueprint_path:
            assert False, f"Unexpected blueprint {path}"
            return orig_load(self, path)

        return models.Blueprint(
            yaml.load_yaml(data_path), expected_domain=self.domain, path=path
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


async def test_notify_leaving_zone(hass):
    """Test notifying leaving a zone blueprint."""

    def set_person_state(state, extra={}):
        hass.states.async_set(
            "person.test_person", state, {"friendly_name": "Paulus", **extra}
        )

    set_person_state("School")

    assert await async_setup_component(
        hass, "zone", {"zone": {"name": "School", "latitude": 1, "longitude": 2}}
    )

    with patch_blueprint(
        "notify_leaving_zone.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "notify_leaving_zone.yaml",
    ):
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": {
                    "use_blueprint": {
                        "path": "notify_leaving_zone.yaml",
                        "input": {
                            "person_entity": "person.test_person",
                            "zone_entity": "zone.school",
                            "notify_device": "abcdefgh",
                        },
                    }
                }
            },
        )

    with patch(
        "homeassistant.components.mobile_app.device_action.async_call_action_from_config"
    ) as mock_call_action:
        # Leaving zone to no zone
        set_person_state("not_home")
        await hass.async_block_till_done()

        assert len(mock_call_action.mock_calls) == 1
        _hass, config, variables, _context = mock_call_action.mock_calls[0][1]
        message_tpl = config.pop("message")
        assert config == {
            "domain": "mobile_app",
            "type": "notify",
            "device_id": "abcdefgh",
        }
        message_tpl.hass = hass
        assert message_tpl.async_render(variables) == "Paulus has left School"

        # Should not increase when we go to another zone
        set_person_state("bla")
        await hass.async_block_till_done()

        assert len(mock_call_action.mock_calls) == 1

        # Should not increase when we go into the zone
        set_person_state("School")
        await hass.async_block_till_done()

        assert len(mock_call_action.mock_calls) == 1

        # Should not increase when we move in the zone
        set_person_state("School", {"extra_key": "triggers change with same state"})
        await hass.async_block_till_done()

        assert len(mock_call_action.mock_calls) == 1

        # Should increase when leaving zone for another zone
        set_person_state("Just Outside School")
        await hass.async_block_till_done()

        assert len(mock_call_action.mock_calls) == 2

        # Verify trigger works
        await hass.services.async_call(
            "automation",
            "trigger",
            {"entity_id": "automation.automation_0"},
            blocking=True,
        )
        assert len(mock_call_action.mock_calls) == 3


async def test_motion_light(hass):
    """Test motion light blueprint."""
    hass.states.async_set("binary_sensor.kitchen", "off")

    with patch_blueprint(
        "motion_light.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "motion_light.yaml",
    ):
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": {
                    "use_blueprint": {
                        "path": "motion_light.yaml",
                        "input": {
                            "light_target": {"entity_id": "light.kitchen"},
                            "motion_entity": "binary_sensor.kitchen",
                        },
                    }
                }
            },
        )

    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    # Turn on motion
    hass.states.async_set("binary_sensor.kitchen", "on")
    # Can't block till done because delay is active
    # So wait 5 event loop iterations to process script
    for _ in range(5):
        await asyncio.sleep(0)

    assert len(turn_on_calls) == 1

    # Test light doesn't turn off if motion stays
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))

    for _ in range(5):
        await asyncio.sleep(0)

    assert len(turn_off_calls) == 0

    # Test light turns off off 120s after last motion
    hass.states.async_set("binary_sensor.kitchen", "off")

    for _ in range(5):
        await asyncio.sleep(0)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    assert len(turn_off_calls) == 1

    # Test restarting the script
    hass.states.async_set("binary_sensor.kitchen", "on")

    for _ in range(5):
        await asyncio.sleep(0)

    assert len(turn_on_calls) == 2
    assert len(turn_off_calls) == 1

    hass.states.async_set("binary_sensor.kitchen", "off")

    for _ in range(5):
        await asyncio.sleep(0)

    hass.states.async_set("binary_sensor.kitchen", "on")

    for _ in range(15):
        await asyncio.sleep(0)

    assert len(turn_on_calls) == 3
    assert len(turn_off_calls) == 1

    # Verify trigger works
    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.automation_0"},
    )
    for _ in range(25):
        await asyncio.sleep(0)
    assert len(turn_on_calls) == 4
