"""Test template blueprints."""
import asyncio
import contextlib
import pathlib
from unittest.mock import patch

import pytest

from homeassistant.components import template
from homeassistant.components.blueprint import models
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

BUILTIN_BLUEPRINT_FOLDER = pathlib.Path(template.__file__).parent / "blueprints"


@contextlib.contextmanager
def patch_blueprint(blueprint_path: str, data_path):
    """Patch blueprint loading from a different source."""
    orig_load = models.DomainBlueprints._load_blueprint

    @callback
    def mock_load_blueprint(self, path):
        if path != blueprint_path:
            pytest.fail(f"Unexpected blueprint {path}")
            return orig_load(self, path)

        return models.Blueprint(
            yaml.load_yaml(data_path), expected_domain=self.domain, path=path
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


async def test_trigger_blueprint_sensor(hass: HomeAssistant) -> None:
    """Test trigger sensor blueprint."""
    hass.states.async_set("binary_sensor.kitchen", "off")

    with patch_blueprint(
        "trigger_template_blueprint_dummy.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "trigger_template_blueprint_dummy.yaml",
    ):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "use_blueprint": {
                        "path": "trigger_template_blueprint_dummy.yaml",
                        "input": {
                            "trigger_entity_id": "binary_sensor.kitchen",
                            "name": "Blueprint trigger template sensor TEST",
                        },
                    }
                }
            },
        )

    await hass.async_block_till_done()

    # Turn on motion
    hass.states.async_set("binary_sensor.kitchen", "on")
    # Can't block till done because delay is active
    # So wait 10 event loop iterations to process script
    for _ in range(10):
        await asyncio.sleep(0)

    # Validate entity creation:
    assert hass.states.get("sensor.blueprint_trigger_template_sensor_test") is not None
    # Validate entity name:
    assert (
        hass.states.get("sensor.blueprint_trigger_template_sensor_test").name
        == "Blueprint trigger template sensor TEST"
    )

    # Turn off motion
    hass.states.async_set("binary_sensor.kitchen", "off")
    # Can't block till done because delay is active
    # So wait 10 event loop iterations to process script
    for _ in range(10):
        await asyncio.sleep(0)

    # Validate state update:
    assert (
        hass.states.get("sensor.blueprint_trigger_template_sensor_test").state
        == "Source state: off"
    )
