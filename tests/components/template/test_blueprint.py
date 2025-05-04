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
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, yaml as yaml_util

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
            yaml_util.load_yaml(data_path),
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


async def test_reload_template_when_blueprint_changes(hass: HomeAssistant) -> None:
    """Test a template is updated at reload if the blueprint has changed."""
    hass.states.async_set("binary_sensor.foo", "on", {"friendly_name": "Foo"})
    config = {
        DOMAIN: [
            {
                "use_blueprint": {
                    "path": "inverted_binary_sensor.yaml",
                    "input": {"reference_entity": "binary_sensor.foo"},
                },
                "name": "Inverted foo",
            },
        ]
    }
    with patch_blueprint(
        "inverted_binary_sensor.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "inverted_binary_sensor.yaml",
    ):
        assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set("binary_sensor.foo", "off", {"friendly_name": "Foo"})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.foo").state == "off"

    inverted = hass.states.get("binary_sensor.inverted_foo")
    assert inverted
    assert inverted.state == "on"

    # Reload the automations without any change, but with updated blueprint
    blueprint_config = yaml_util.load_yaml(
        BUILTIN_BLUEPRINT_FOLDER / "inverted_binary_sensor.yaml"
    )
    blueprint_config["binary_sensor"]["state"] = "{{ states(reference_entity) }}"
    with (
        patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ),
        patch(
            "homeassistant.components.blueprint.models.yaml_util.load_yaml_dict",
            autospec=True,
            return_value=blueprint_config,
        ),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    hass.states.async_set("binary_sensor.foo", "off", {"friendly_name": "Foo"})
    await hass.async_block_till_done()

    not_inverted = hass.states.get("binary_sensor.inverted_foo")
    assert not_inverted
    assert not_inverted.state == "off"

    hass.states.async_set("binary_sensor.foo", "on", {"friendly_name": "Foo"})
    await hass.async_block_till_done()

    not_inverted = hass.states.get("binary_sensor.inverted_foo")
    assert not_inverted
    assert not_inverted.state == "on"


@pytest.mark.parametrize(
    ("blueprint"),
    ["test_event_sensor.yaml", "test_event_sensor_legacy_schema.yaml"],
)
async def test_trigger_event_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    blueprint: str,
) -> None:
    """Test event sensor blueprint."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "use_blueprint": {
                        "path": blueprint,
                        "input": {
                            "event_type": "my_custom_event",
                            "event_data": {"foo": "bar"},
                        },
                    },
                    "name": "My Custom Event",
                },
            ]
        },
    )

    context = Context()
    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire(
            "my_custom_event", {"foo": "bar", "beer": 2}, context=context
        )
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.my_custom_event")
    assert date_state is not None
    assert date_state.state == now.isoformat(timespec="seconds")
    data = date_state.attributes.get("data")
    assert data is not None
    assert data != ""
    assert data.get("foo") == "bar"
    assert data.get("beer") == 2

    inverted_foo_template = template.helpers.blueprint_in_template(
        hass, "sensor.my_custom_event"
    )
    assert inverted_foo_template == blueprint

    inverted_binary_sensor_blueprint_entity_ids = (
        template.helpers.templates_with_blueprint(hass, blueprint)
    )
    assert len(inverted_binary_sensor_blueprint_entity_ids) == 1

    with pytest.raises(BlueprintInUse):
        await template.async_get_blueprints(hass).async_remove_blueprint(blueprint)


@pytest.mark.parametrize(
    ("blueprint", "override"),
    [
        # Override a blueprint with modern schema with legacy schema
        (
            "test_event_sensor.yaml",
            {"trigger": {"platform": "event", "event_type": "override"}},
        ),
        # Override a blueprint with modern schema with modern schema
        (
            "test_event_sensor.yaml",
            {"triggers": {"platform": "event", "event_type": "override"}},
        ),
        # Override a blueprint with legacy schema with legacy schema
        (
            "test_event_sensor_legacy_schema.yaml",
            {"trigger": {"platform": "event", "event_type": "override"}},
        ),
        # Override a blueprint with legacy schema with modern schema
        (
            "test_event_sensor_legacy_schema.yaml",
            {"triggers": {"platform": "event", "event_type": "override"}},
        ),
    ],
)
async def test_blueprint_template_override(
    hass: HomeAssistant, blueprint: str, override: dict
) -> None:
    """Test blueprint template where the template config overrides the blueprint."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "use_blueprint": {
                        "path": blueprint,
                        "input": {
                            "event_type": "my_custom_event",
                            "event_data": {"foo": "bar"},
                        },
                    },
                    "name": "My Custom Event",
                }
                | override,
            ]
        },
    )
    await hass.async_block_till_done()

    date_state = hass.states.get("sensor.my_custom_event")
    assert date_state is not None
    assert date_state.state == "unknown"

    context = Context()
    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire(
            "my_custom_event", {"foo": "bar", "beer": 2}, context=context
        )
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.my_custom_event")
    assert date_state is not None
    assert date_state.state == "unknown"

    context = Context()
    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.now", return_value=now):
        hass.bus.async_fire("override", {"foo": "bar", "beer": 2}, context=context)
        await hass.async_block_till_done()

    date_state = hass.states.get("sensor.my_custom_event")
    assert date_state is not None
    assert date_state.state == now.isoformat(timespec="seconds")
    data = date_state.attributes.get("data")
    assert data is not None
    assert data != ""
    assert data.get("foo") == "bar"
    assert data.get("beer") == 2

    inverted_foo_template = template.helpers.blueprint_in_template(
        hass, "sensor.my_custom_event"
    )
    assert inverted_foo_template == blueprint

    inverted_binary_sensor_blueprint_entity_ids = (
        template.helpers.templates_with_blueprint(hass, blueprint)
    )
    assert len(inverted_binary_sensor_blueprint_entity_ids) == 1

    with pytest.raises(BlueprintInUse):
        await template.async_get_blueprints(hass).async_remove_blueprint(blueprint)


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
    blueprints = await template.async_get_blueprints(hass).async_get_blueprints()
    assert "invalid.yaml" not in blueprints


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
