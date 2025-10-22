"""Test blueprints."""

from collections.abc import Iterator
import contextlib
from os import PathLike
import pathlib
from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.asyncio

from homeassistant.components import template
from homeassistant.components.blueprint import (
    BLUEPRINT_SCHEMA,
    Blueprint,
    BlueprintInUse,
    DomainBlueprints,
)
from homeassistant.components.template import DOMAIN, SERVICE_RELOAD
from homeassistant.components.template.config import (
    DOMAIN_ALARM_CONTROL_PANEL,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_COVER,
    DOMAIN_FAN,
    DOMAIN_IMAGE,
    DOMAIN_LIGHT,
    DOMAIN_LOCK,
    DOMAIN_NUMBER,
    DOMAIN_SELECT,
    DOMAIN_SENSOR,
    DOMAIN_SWITCH,
    DOMAIN_VACUUM,
    DOMAIN_WEATHER,
)
from homeassistant.const import STATE_ON
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.template import Template
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


@pytest.mark.parametrize(
    ("domain", "set_state", "expected"),
    [
        (DOMAIN_ALARM_CONTROL_PANEL, STATE_ON, "armed_home"),
        (DOMAIN_BINARY_SENSOR, STATE_ON, STATE_ON),
        (DOMAIN_COVER, STATE_ON, "open"),
        (DOMAIN_FAN, STATE_ON, STATE_ON),
        (DOMAIN_IMAGE, "test.jpg", "2025-06-13T00:00:00+00:00"),
        (DOMAIN_LIGHT, STATE_ON, STATE_ON),
        (DOMAIN_LOCK, STATE_ON, "locked"),
        (DOMAIN_NUMBER, "1", "1.0"),
        (DOMAIN_SELECT, "option1", "option1"),
        (DOMAIN_SENSOR, "foo", "foo"),
        (DOMAIN_SWITCH, STATE_ON, STATE_ON),
        (DOMAIN_VACUUM, "cleaning", "cleaning"),
        (DOMAIN_WEATHER, "sunny", "sunny"),
    ],
)
@pytest.mark.freeze_time("2025-06-13 00:00:00+00:00")
async def test_variables_for_entity(
    hass: HomeAssistant, domain: str, set_state: str, expected: str
) -> None:
    """Test regular template entities via blueprint with variables defined."""
    hass.states.async_set("sensor.test_state", set_state)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "use_blueprint": {
                        "path": f"test_{domain}_with_variables.yaml",
                        "input": {"sensor": "sensor.test_state"},
                    },
                    "name": "Test",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.state == expected

async def test_blueprint_variables_load_on_reload(hass):
    """Test that blueprint variables are correctly loaded on reload."""

    # S-1: mock a template blueprint config with a variable
    config = {
        "template": {
            "trigger": {"platform": "state", "entity_id": "sensor.test"},
            "sensor": {
                "name": "Test Sensor",
                "state": "{{ my_var }}",
                "variables": {"my_var": "loaded"},
            },
        }
    }

    # S-2: setup template component
    assert await async_setup_component(hass, "template", config)
    await hass.async_block_till_done()

    # S-3: verify that the variable was loaded
    state = hass.states.get("sensor.test_sensor")
    assert state is not None
    assert state.state == "loaded"

    # S-4: simulate reload
    await hass.services.async_call("homeassistant", "reload", blocking=True)
    await hass.async_block_till_done()

    # S-5: verify variable still loaded after reload
    state = hass.states.get("sensor.test_sensor")
    assert state.state == "loaded"

