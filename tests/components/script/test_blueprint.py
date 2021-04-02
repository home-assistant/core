"""Test script blueprints."""
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


async def test_random_color(hass: HomeAssistant) -> None:
    """Test motion light blueprint."""
    with patch_blueprint(
        "random_color.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "random_color.yaml",
    ):
        assert await async_setup_component(
            hass,
            script.DOMAIN,
            {
                "script": {
                    "roll_dice": {
                        "use_blueprint": {
                            "path": "random_color.yaml",
                            "input": {
                                "default_target": {"entity_id": "light.kitchen"},
                                "colors": ["red", "white", "blue"],
                            },
                        }
                    }
                }
            },
        )

    turn_on_calls = async_mock_service(hass, "light", "turn_on")

    # Trigger random color
    await hass.services.async_call(script.DOMAIN, "roll_dice", blocking=True)

    assert len(turn_on_calls) == 1
    call = turn_on_calls[0]
    assert call.data["color_name"] in ["red", "white", "blue"]
    assert call.data["entity_id"] == ["light.kitchen"]

    # Trigger random color, override target
    await hass.services.async_call(
        script.DOMAIN,
        "roll_dice",
        {"target": {"entity_id": "light.living_room"}},
        blocking=True,
    )

    assert len(turn_on_calls) == 2
    call = turn_on_calls[1]
    assert call.data["color_name"] in ["red", "white", "blue"]
    assert call.data["entity_id"] == ["light.living_room"]
