"""template conftest."""

from dataclasses import dataclass
from enum import Enum, StrEnum

import pytest

from homeassistant.components import template
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.conftest import WebSocketGenerator


class ConfigurationStyle(Enum):
    """Configuration Styles for template testing."""

    LEGACY = "Legacy"
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
                "entity_id": list(entities),
            },
            {"platform": "event", "event_type": "test_event"},
        ],
        "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
        "action": [
            {"event": "action_event", "event_data": {"what": "{{ triggering_entity }}"}}
        ],
    }


async def async_trigger(
    hass: HomeAssistant,
    entity_id: str,
    state: str | None = None,
    attributes: dict | None = None,
) -> None:
    """Trigger a state change."""
    hass.states.async_set(entity_id, state, attributes)
    await hass.async_block_till_done()


async def async_setup_legacy_platforms(
    hass: HomeAssistant,
    domain: str,
    slug: str | None,
    count: int,
    config: ConfigType | list[ConfigType],
) -> None:
    """Do setup of any legacy platform that supports a keyed dictionary of template entities."""
    if slug is None:
        # Lock and Weather platforms do not use a slug
        if isinstance(config, list):
            config = {domain: [{"platform": "template", **item} for item in config]}
        else:
            config = {domain: {"platform": "template", **config}}
    else:
        assert isinstance(config, dict)
        config = {domain: {"platform": "template", slug: config}}

    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
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
    legacy_slug: str | None
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
    if style == ConfigurationStyle.LEGACY:
        entity_config = {
            **({"value_template": state_template} if state_template else {}),
            **config,
            **(extra_config or {}),
            **({"attribute_templates": attributes} if attributes else {}),
        }
        # Lock and weather platforms do not use a slug.
        if platform_setup.legacy_slug is None:
            config = {"name": platform_setup.object_id, **entity_config}
        else:
            config = {platform_setup.object_id: entity_config}

        await async_setup_legacy_platforms(
            hass, platform_setup.domain, platform_setup.legacy_slug, count, config
        )
        return

    entity_config = {
        "name": platform_setup.object_id,
        **({"state": state_template} if state_template else {}),
        **config,
        **({"attributes": attributes} if attributes else {}),
        **(extra_config or {}),
    }
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(
            hass, platform_setup.domain, count, entity_config, extra_section_config
        )
    elif style == ConfigurationStyle.TRIGGER:
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
    if style == ConfigurationStyle.LEGACY:
        state_config = {"value_template": state_template} if state_template else {}
        entity_config = {
            "unique_id": "not-so_-unique-anymore",
            **(entity_config or {}),
            **state_config,
        }
        if platform_setup.legacy_slug is None:
            config = [
                {"name": "template_entity_1", **entity_config},
                {"name": "template_entity_2", **entity_config},
            ]
        else:
            config = {
                "template_entity_1": entity_config,
                "template_entity_2": entity_config,
            }
        await async_setup_legacy_platforms(
            hass, platform_setup.domain, platform_setup.legacy_slug, 1, config
        )
        return

    state_config = {"state": state_template} if state_template else {}
    entity_config = {
        "unique_id": "not-so_-unique-anymore",
        **(entity_config or {}),
        **state_config,
    }
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(
            hass,
            platform_setup.domain,
            1,
            [
                {"name": "template_entity_1", **entity_config},
                {"name": "template_entity_2", **entity_config},
            ],
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_modern_trigger_format(
            hass,
            platform_setup.domain,
            platform_setup.trigger,
            1,
            [
                {"name": "template_entity_1", **entity_config},
                {"name": "template_entity_2", **entity_config},
            ],
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
    """Setup 2 entities with unique unique_ids in a template section that contains a unique_id.

    The test will verify that 2 entities are created where the unique_id appends the
    section unique_id to each entity unique_id.

    The entity_config should not provide name or unique_id, those are added automatically.
    """
    state_config = {"state": state_template} if state_template else {}
    entities = [
        {"name": "test_a", "unique_id": "a", **(entity_config or {}), **state_config},
        {"name": "test_b", "unique_id": "b", **(entity_config or {}), **state_config},
    ]
    extra_section_config = {"unique_id": "x"}
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(
            hass, platform_setup.domain, 1, entities, extra_section_config
        )
    elif style == ConfigurationStyle.TRIGGER:
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
