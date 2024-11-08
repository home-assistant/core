"""Test blueprints."""

from collections.abc import Iterator
import contextlib
from os import PathLike
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import template
from homeassistant.components.blueprint import (
    BLUEPRINT_SCHEMA,
    Blueprint,
    BlueprintInUse,
    DomainBlueprints,
)
from homeassistant.components.template import DOMAIN, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

from tests.common import async_mock_service

BUILTIN_BLUEPRINT_FOLDER = pathlib.Path(template.__file__).parent / "blueprints"


@contextlib.contextmanager
def patch_blueprint(
    blueprint_path: str, data_path: str | PathLike[str]
) -> Iterator[None]:
    """Patch blueprint loading from a different source."""
    orig_load = DomainBlueprints._load_blueprint

    @callback
    def mock_load_blueprint(self, path):
        if path != blueprint_path:
            pytest.fail(f"Unexpected blueprint {path}")
            return orig_load(self, path)

        return Blueprint(
            yaml.load_yaml(data_path),
            expected_domain=self.domain,
            path=path,
            schema=BLUEPRINT_SCHEMA,
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


@contextlib.contextmanager
def patch_invalid_blueprint() -> Iterator[None]:
    """Patch blueprint returning an invalid one."""

    @callback
    def mock_load_blueprint(self, path):
        return Blueprint(
            {
                "blueprint": {
                    "domain": "template",
                    "name": "Invalid template blueprint",
                },
                "binary_sensor": {},
                "sensor": {},
            },
            expected_domain=self.domain,
            path=path,
            schema=BLUEPRINT_SCHEMA,
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


async def test_inverted_binary_sensor(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test inverted binary sensor blueprint."""
    hass.states.async_set("binary_sensor.foo", "on", {"friendly_name": "Foo"})
    hass.states.async_set("binary_sensor.bar", "off", {"friendly_name": "Bar"})

    with patch_blueprint(
        "inverted_binary_sensor.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "inverted_binary_sensor.yaml",
    ):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": [
                    {
                        "use_blueprint": {
                            "path": "inverted_binary_sensor.yaml",
                            "input": {"reference_entity": "binary_sensor.foo"},
                        },
                        "name": "Inverted foo",
                    },
                    {
                        "use_blueprint": {
                            "path": "inverted_binary_sensor.yaml",
                            "input": {"reference_entity": "binary_sensor.bar"},
                        },
                        "name": "Inverted bar",
                    },
                ]
            },
        )

    hass.states.async_set("binary_sensor.foo", "off", {"friendly_name": "Foo"})
    hass.states.async_set("binary_sensor.bar", "on", {"friendly_name": "Bar"})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.foo").state == "off"
    assert hass.states.get("binary_sensor.bar").state == "on"

    inverted_foo = hass.states.get("binary_sensor.inverted_foo")
    assert inverted_foo
    assert inverted_foo.state == "on"

    inverted_bar = hass.states.get("binary_sensor.inverted_bar")
    assert inverted_bar
    assert inverted_bar.state == "off"

    foo_template = template.helpers.blueprint_in_template(hass, "binary_sensor.foo")
    inverted_foo_template = template.helpers.blueprint_in_template(
        hass, "binary_sensor.inverted_foo"
    )
    assert foo_template is None
    assert inverted_foo_template == "inverted_binary_sensor.yaml"

    inverted_binary_sensor_blueprint_entity_ids = (
        template.helpers.templates_with_blueprint(hass, "inverted_binary_sensor.yaml")
    )
    assert len(inverted_binary_sensor_blueprint_entity_ids) == 2

    assert len(template.helpers.templates_with_blueprint(hass, "dummy.yaml")) == 0

    with pytest.raises(BlueprintInUse):
        await template.async_get_blueprints(hass).async_remove_blueprint(
            "inverted_binary_sensor.yaml"
        )


async def test_domain_blueprint(hass: HomeAssistant) -> None:
    """Test DomainBlueprint services."""
    reload_handler_calls = async_mock_service(hass, DOMAIN, SERVICE_RELOAD)
    mock_create_file = MagicMock()
    mock_create_file.return_value = True

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._create_file",
        mock_create_file,
    ):
        await template.async_get_blueprints(hass).async_add_blueprint(
            Blueprint(
                {
                    "blueprint": {
                        "domain": DOMAIN,
                        "name": "Test",
                    },
                },
                expected_domain="template",
                path="xxx",
                schema=BLUEPRINT_SCHEMA,
            ),
            "xxx",
            True,
        )
    assert len(reload_handler_calls) == 1


async def test_invalid_blueprint(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an invalid blueprint definition."""

    with patch_invalid_blueprint():
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": [
                    {
                        "use_blueprint": {
                            "path": "invalid.yaml",
                        },
                        "name": "Invalid blueprint instance",
                    },
                ]
            },
        )

    assert "more than one platform defined per blueprint" in caplog.text
    assert await template.async_get_blueprints(hass).async_get_blueprints() == {}


async def test_no_blueprint(hass: HomeAssistant) -> None:
    """Test templates without blueprints."""
    with patch_blueprint(
        "inverted_binary_sensor.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "inverted_binary_sensor.yaml",
    ):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": [
                    {"binary_sensor": {"name": "test entity", "state": "off"}},
                    {
                        "use_blueprint": {
                            "path": "inverted_binary_sensor.yaml",
                            "input": {"reference_entity": "binary_sensor.foo"},
                        },
                        "name": "inverted entity",
                    },
                ]
            },
        )

    hass.states.async_set("binary_sensor.foo", "off", {"friendly_name": "Foo"})
    await hass.async_block_till_done()

    assert (
        len(
            template.helpers.templates_with_blueprint(
                hass, "inverted_binary_sensor.yaml"
            )
        )
        == 1
    )
    assert (
        template.helpers.blueprint_in_template(hass, "binary_sensor.test_entity")
        is None
    )
