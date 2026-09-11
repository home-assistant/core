"""template conftest."""

from dataclasses import dataclass
from enum import Enum, StrEnum
from itertools import chain
from unittest.mock import AsyncMock, Mock

import pytest
import voluptuous as vol

from homeassistant.components import template
from homeassistant.components.device_automation import toggle_entity
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_mock_service,
    mock_platform,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)
from tests.conftest import WebSocketGenerator

_TEST_EXTRA_ATTRIBUTES_ENTITY_ID = "sensor.test_extra_attributes"


class ConfigurationStyle(Enum):
    """Configuration Styles for template testing."""

    MODERN = "Modern"
    TRIGGER = "Trigger"


class Brewery(StrEnum):
    """Test enum."""

    MMMM = "mmmm"
    BEER = "beer"
    IS = "is"
    GOOD = "good"


def make_test_trigger(*entities: str) -> dict:
    """Make a test state trigger."""
    return {
        "trigger": [
            {
                "trigger": "state",
                "entity_id": list(chain(entities, (_TEST_EXTRA_ATTRIBUTES_ENTITY_ID,))),
            },
            {"platform": "event", "event_type": "test_event"},
        ],
        "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
        "action": [
            {"event": "action_event", "event_data": {"what": "{{ triggering_entity }}"}}
        ],
    }


def make_test_action(action: str, extra_data: ConfigType | None = None) -> ConfigType:
    """Make a test action."""
    data = extra_data or {}
    return {
        action: {
            "action": "test.automation",
            "data": {"caller": "{{ this.entity_id }}", "action": action, **data},
        }
    }


def make_mock_device_actions(
    actions: list[str],
    platform_setup: TemplatePlatformSetup,
    device_entry: dr.DeviceEntry,
    entity_entry: er.RegistryEntry,
) -> ConfigType:
    """Make actions for device testing."""
    return {
        action: [
            {
                "action": "test.automation",
                "data": {
                    "action": "fake_action",
                    "caller": platform_setup.entity_id,
                },
            },
            {
                "domain": "fake_integration",
                "type": "turn_on",
                "device_id": device_entry.id,
                "entity_id": entity_entry.id,
                "metadata": {"secondary": False},
            },
        ]
        for action in actions
    }


async def setup_mock_devices(
    hass: HomeAssistant,
    domain: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> tuple[TemplatePlatformSetup, dr.DeviceEntry, er.RegistryEntry]:
    """Setup mock devices for testing."""
    FAKE_DOMAIN = "fake_integration"

    hass.config.components.add(FAKE_DOMAIN)

    async def _async_get_actions(
        hass: HomeAssistant, device_id: str
    ) -> list[dict[str, str]]:
        """List device actions."""
        return await toggle_entity.async_get_actions(hass, device_id, FAKE_DOMAIN)

    mock_platform(
        hass,
        f"{FAKE_DOMAIN}.device_action",
        Mock(
            ACTION_SCHEMA=toggle_entity.ACTION_SCHEMA.extend(
                {vol.Required("domain"): FAKE_DOMAIN}
            ),
            async_get_actions=_async_get_actions,
            async_call_action_from_config=AsyncMock(),
            spec=[
                "ACTION_SCHEMA",
                "async_get_actions",
                "async_call_action_from_config",
            ],
        ),
    )
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    await hass.async_block_till_done()

    platform_setup = TemplatePlatformSetup(
        domain, "test_entity", make_test_trigger("sensor.trigger")
    )
    return (platform_setup, device_entry, entity_entry)


def assert_action(
    platform_setup: TemplatePlatformSetup,
    calls: list[ServiceCall],
    expected_calls: int,
    expected_action: str,
    index: int = -1,
    **kwargs,
) -> None:
    """Validate the action was properly called."""
    assert len(calls) == expected_calls
    assert calls[index].data["action"] == expected_action
    assert calls[index].data["caller"] == platform_setup.entity_id
    for key, value in kwargs.items():
        assert calls[index].data[key] == value


async def async_trigger(
    hass: HomeAssistant,
    entity_id: str,
    state: str | None = None,
    attributes: dict | None = None,
) -> None:
    """Trigger a state change."""
    hass.states.async_set(entity_id, state, attributes)
    await hass.async_block_till_done()


async def async_setup_modern_state_format(
    hass: HomeAssistant,
    domain: str,
    count: int,
    config: ConfigType | list[ConfigType],
    extra_section_config: ConfigType | None = None,
) -> None:
    """Do setup of template integration via modern format."""
    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {"template": {domain: config, **(extra_section_config or {})}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_trigger_format(
    hass: HomeAssistant,
    domain: str,
    trigger: dict,
    count: int,
    config: ConfigType | list[ConfigType],
    extra_section_config: ConfigType | None = None,
) -> None:
    """Do setup of template integration via trigger format."""
    config = {"template": {domain: config, **trigger, **(extra_section_config or {})}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@dataclass(frozen=True)
class TemplatePlatformSetup:
    """Template Platform Setup Information."""

    domain: str
    object_id: str
    trigger: ConfigType

    @property
    def entity_id(self) -> str:
        """Return test entity ID."""
        return f"{self.domain}.{self.object_id}"


async def setup_entity(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    count: int,
    config: ConfigType,
    state_template: str | None = None,
    extra_config: ConfigType | None = None,
    attributes: ConfigType | None = None,
    extra_section_config: ConfigType | None = None,
) -> None:
    """Do setup of a template entity based on the configuration style."""
    entity_config = {
        "name": platform_setup.object_id,
        **({"state": state_template} if state_template else {}),
        **config,
        **({"attributes": attributes} if attributes else {}),
        **(extra_config or {}),
    }
    if style is ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(
            hass, platform_setup.domain, count, entity_config, extra_section_config
        )
    elif style is ConfigurationStyle.TRIGGER:
        await async_setup_modern_trigger_format(
            hass,
            platform_setup.domain,
            platform_setup.trigger,
            count,
            entity_config,
            extra_section_config,
        )


async def setup_and_test_unique_id(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    entity_config: ConfigType | None,
    state_template: str | None = None,
) -> None:
    """Setup 2 entities with the same unique_id and verify only 1 entity is created.

    The entity_config not provide name or unique_id, those are added automatically.
    """
    state_config = {"state": state_template} if state_template else {}
    entity_config = {
        "unique_id": "not-so_-unique-anymore",
        **(entity_config or {}),
        **state_config,
    }
    entities = [
        {"name": "template_entity_1", **entity_config},
        {"name": "template_entity_2", **entity_config},
    ]
    if style is ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(hass, platform_setup.domain, 1, entities)
    elif style is ConfigurationStyle.TRIGGER:
        await async_setup_modern_trigger_format(
            hass, platform_setup.domain, platform_setup.trigger, 1, entities
        )

    assert len(hass.states.async_all(platform_setup.domain)) == 1


async def setup_and_test_nested_unique_id(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    entity_registry: er.EntityRegistry,
    entity_config: ConfigType | None,
    state_template: str | None = None,
) -> None:
    """Setup 2 entities with unique_ids in a template section with a unique_id.

    The test will verify that 2 entities are created where the unique_id
    appends the section unique_id to each entity unique_id.

    The entity_config should not provide name or unique_id, those are
    added automatically.
    """
    state_config = {"state": state_template} if state_template else {}
    entities = [
        {"name": "test_a", "unique_id": "a", **(entity_config or {}), **state_config},
        {"name": "test_b", "unique_id": "b", **(entity_config or {}), **state_config},
    ]
    extra_section_config = {"unique_id": "x"}
    if style is ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(
            hass, platform_setup.domain, 1, entities, extra_section_config
        )
    elif style is ConfigurationStyle.TRIGGER:
        await async_setup_modern_trigger_format(
            hass,
            platform_setup.domain,
            platform_setup.trigger,
            1,
            entities,
            extra_section_config,
        )

    assert len(hass.states.async_all(platform_setup.domain)) == 2

    entry = entity_registry.async_get(f"{platform_setup.domain}.test_a")
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get(f"{platform_setup.domain}.test_b")
    assert entry.unique_id == "x-b"


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def start_ha(
    hass: HomeAssistant, count: int, domain: str, config: ConfigType
) -> None:
    """Do setup of integration."""
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def caplog_setup_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return setup log of integration."""
    return caplog.text


def _create_bad_action_config(action: str, config: ConfigType) -> ConfigType:
    """Create a bad device action."""
    return {
        action: {
            "type": "turn_off",
            "device_id": "70c5f67ec2f82f9ba128fe6e99eb7dfa",
            "entity_id": "c7e6f3753cb18937f2147bbbdccdd949",
            "domain": "light",
        },
        **config,
    }


async def assert_invalid_yaml_actions_do_not_create_entities(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    config: ConfigType,
    action: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Assert invalid yaml actions on entity services do not create entities."""

    await setup_entity(
        hass,
        platform_setup,
        style,
        1,
        {
            "default_entity_id": platform_setup.entity_id,
            **_create_bad_action_config(action, config),
        },
    )
    assert len(hass.states.async_all(platform_setup.domain)) == 0

    error = f"The '{action}' actions for {platform_setup.object_id} failed to setup: Unknown device '70c5f67ec2f82f9ba128fe6e99eb7dfa'"
    assert error in caplog.text


async def assert_invalid_config_entry_actions_do_not_create_entities(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    config: ConfigType,
    action: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Assert invalid config entry actions on entity services do not create entities."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": platform_setup.object_id,
            "template_type": platform_setup.domain,
            **_create_bad_action_config(action, config),
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(platform_setup.domain)) == 0

    error = f"The '{action}' actions for {platform_setup.object_id} failed to setup: Unknown device '70c5f67ec2f82f9ba128fe6e99eb7dfa'"
    assert error in caplog.text


async def async_get_flow_preview_state(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    domain: str,
    user_input: ConfigType,
) -> ConfigType:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        template.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": domain},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == domain
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    return msg["event"]


def assert_state_and_attributes(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    expected_state: str | None = None,
    expected_attributes: ConfigType | None = None,
) -> State:
    """Assert expected state and attributes."""

    state = hass.states.get(platform_setup.entity_id)
    assert state is not None
    assert state.state == expected_state or expected_state is None

    expected_attributes = expected_attributes or {}
    for attribute, value in expected_attributes.items():
        assert state.attributes.get(attribute) == value
    return state


RESTORE_STATE_SAVED_ATTRIBUTES = {
    "friendly_name": "Restored Name",
    "icon": "mdi:restored",
    "entity_picture": "local/restored.png",
}
RESTORE_STATE_UPDATED_ATTRIBUTES = {
    "friendly_name": "Updated Name",
    "icon": "mdi:updated",
    "entity_picture": "local/updated.png",
}


def make_restore_state_built_in_attribute_templates(jinja_test: str) -> dict:
    """Make built in attribute templates for restore state testing."""
    return {
        "name": f"{{% if {jinja_test} %}}Updated Name{{% endif %}}",
        "picture": f"{{% if {jinja_test} %}}local/updated.png{{% endif %}}",
        "icon": f"{{% if {jinja_test} %}}mdi:updated{{% endif %}}",
    }


def setup_mock_template_entity_restore_state(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    saved_state: str,
    saved_extra_data: ConfigType | None = None,
    saved_attributes: ConfigType | None = None,
) -> None:
    """Setup an entity and verify state is restored."""
    saved_attributes = {
        **RESTORE_STATE_SAVED_ATTRIBUTES,
        **(saved_attributes or {}),
    }

    fake_state = State(
        platform_setup.entity_id,
        saved_state,
        saved_attributes,
    )
    if saved_extra_data is not None:
        mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))
    else:
        mock_restore_cache(hass, (fake_state,))


async def setup_restore_template_entity(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    config: ConfigType,
    jinja_test: str = "is_state('sensor.test_restore', 'on')",
) -> None:
    """Test that state and attributes are restored from the last state."""
    default_entity_id = platform_setup.entity_id

    await setup_entity(
        hass,
        platform_setup,
        style,
        1,
        config={
            "default_entity_id": default_entity_id,
            **make_restore_state_built_in_attribute_templates(jinja_test),
            **config,
        },
    )


async def assert_extra_template_attributes(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Test extra template attributes and attribute order."""

    # Trigger attributes are resolved in order, Modern are not.
    setup_attributes = {
        ConfigurationStyle.MODERN: {},
        ConfigurationStyle.TRIGGER: {
            "base": "{{ state_attr('sensor.test_extra_attributes', 'base') or 0 }}",
            "plus_one": "{{ base + 1 }}",
        },
    }

    await setup_entity(
        hass,
        platform_setup,
        style,
        1,
        {
            **config,
            "attributes": {
                "static": "{{ 'static' }}",
                "dynamic": "It {{ state_attr('sensor.test_extra_attributes', 'dynamic') }}.",
                **setup_attributes[style],
            },
        },
    )

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "dynamic": "",
            "base": 1,
        },
    )

    state = hass.states.get(platform_setup.entity_id)
    assert state.attributes["static"] == "static"
    assert state.attributes["dynamic"] == "It ."

    # Assert attribute order for trigger entities
    for attr, value in (
        ("base", 1),
        ("plus_one", 2),
    ):
        assert (
            attr not in state.attributes and style == ConfigurationStyle.MODERN
        ) or state.attributes[attr] == value

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "dynamic": "works",
            "base": 2,
        },
    )

    state = hass.states.get(platform_setup.entity_id)
    assert state.attributes["static"] == "static"
    assert state.attributes["dynamic"] == "It works."
    for attr, value in (
        ("base", 2),
        ("plus_one", 3),
    ):
        assert (
            attr not in state.attributes and style == ConfigurationStyle.MODERN
        ) or state.attributes[attr] == value


async def assert_attributes_template(
    hass: HomeAssistant,
    platform_setup: TemplatePlatformSetup,
    style: ConfigurationStyle,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test extra attributes template."""

    await setup_entity(
        hass,
        platform_setup,
        style,
        1,
        {
            **config,
            "attributes": "{{ state_attr('sensor.test_extra_attributes', 'attributes') or {} }}",
        },
    )

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "attributes": {"beer": "empty", "happiness": "low"},
        },
    )

    state = hass.states.get(platform_setup.entity_id)
    assert state.attributes["beer"] == "empty"
    assert "level" not in state.attributes
    assert state.attributes["happiness"] == "low"

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "attributes": {"beer": "full", "level": 100, "happiness": "high"},
        },
    )

    state = hass.states.get(platform_setup.entity_id)
    assert state.attributes["beer"] == "full"
    assert state.attributes["level"] == 100
    assert state.attributes["happiness"] == "high"

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "attributes": {"run": True},
        },
    )
    state = hass.states.get(platform_setup.entity_id)
    assert state.attributes["run"] is True
    assert "beer" not in state.attributes
    assert "level" not in state.attributes
    assert "happiness" not in state.attributes

    error = "Error validating template result"
    assert error not in caplog.text

    await async_trigger(
        hass,
        _TEST_EXTRA_ATTRIBUTES_ENTITY_ID,
        "anything",
        {
            "attributes": ["not a dict"],
        },
    )

    assert error in caplog.text
    state = hass.states.get(platform_setup.entity_id)
    assert "run" not in state.attributes
