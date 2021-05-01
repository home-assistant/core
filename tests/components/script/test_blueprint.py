"""Test script blueprints."""
import asyncio
import contextlib
import pathlib
from typing import Iterator
from unittest.mock import patch

from homeassistant.components import script
from homeassistant.components.blueprint.models import Blueprint, DomainBlueprints
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

from tests.common import async_mock_service

BUILTIN_BLUEPRINT_FOLDER = pathlib.Path(script.__file__).parent / "blueprints"


@contextlib.contextmanager
def patch_blueprint(blueprint_path: str, data_path: str) -> Iterator[None]:
    """Patch blueprint loading from a different source."""
    orig_load = DomainBlueprints._load_blueprint

    @callback
    def mock_load_blueprint(self, path: str) -> Blueprint:
        if path != blueprint_path:
            assert False, f"Unexpected blueprint {path}"
            return orig_load(self, path)

        return Blueprint(
            yaml.load_yaml(data_path), expected_domain=self.domain, path=path
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


async def test_confirmable_notification(hass: HomeAssistant) -> None:
    """Test confirmable notification blueprint."""
    with patch_blueprint(
        "confirmable_notification.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "confirmable_notification.yaml",
    ):
        assert await async_setup_component(
            hass,
            script.DOMAIN,
            {
                "script": {
                    "confirm": {
                        "use_blueprint": {
                            "path": "confirmable_notification.yaml",
                            "input": {
                                "notify_device": "frodo",
                                "title": "Lord of the things",
                                "message": "Throw ring in mountain?",
                                "confirm_action": [
                                    {
                                        "service": "homeassistant.turn_on",
                                        "target": {"entity_id": "mount.doom"},
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        )

    turn_on_calls = async_mock_service(hass, "homeassistant", "turn_on")

    with patch(
        "homeassistant.components.mobile_app.device_action.async_call_action_from_config"
    ) as mock_call_action:

        # Trigger script
        await hass.services.async_call(script.DOMAIN, "confirm")

        # Give script the time to attach the trigger.
        await asyncio.sleep(0.1)

    hass.bus.async_fire("mobile_app_notification_action", {"action": "CONFIRM"})
    await hass.async_block_till_done()

    assert len(mock_call_action.mock_calls) == 1
    _hass, config, variables, _context = mock_call_action.mock_calls[0][1]

    title_tpl = config.pop("title")
    message_tpl = config.pop("message")
    title_tpl.hass = hass
    message_tpl.hass = hass

    assert config == {
        "alias": "Send notification",
        "domain": "mobile_app",
        "type": "notify",
        "device_id": "frodo",
        "data": {
            "actions": [
                {"action": "CONFIRM", "title": "Confirm"},
                {"action": "DISMISS", "title": "Dismiss"},
            ]
        },
    }

    assert title_tpl.async_render(variables) == "Lord of the things"
    assert message_tpl.async_render(variables) == "Throw ring in mountain?"

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data == {
        "entity_id": ["mount.doom"],
    }
