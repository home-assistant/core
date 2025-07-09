"""template conftest."""

from enum import Enum

import pytest

from homeassistant.components import template
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.conftest import WebSocketGenerator


class ConfigurationStyle(Enum):
    """Configuration Styles for template testing."""

    LEGACY = "Legacy"
    MODERN = "Modern"
    TRIGGER = "Trigger"


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


async def async_setup_legacy_platforms(
    hass: HomeAssistant,
    domain: str,
    slug: str,
    count: int,
    config: ConfigType,
) -> None:
    """Do setup of any legacy platform that supports a keyed dictionary of template entities."""
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            {domain: {"platform": "template", slug: config}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_state_format(
    hass: HomeAssistant,
    domain: str,
    count: int,
    config: ConfigType,
    extra_config: ConfigType | None = None,
) -> None:
    """Do setup of template integration via modern format."""
    extra = extra_config or {}
    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {"template": {domain: config, **extra}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_trigger_format(
    hass: HomeAssistant,
    domain: str,
    trigger: dict,
    count: int,
    config: ConfigType,
    extra_config: ConfigType | None = None,
) -> None:
    """Do setup of template integration via trigger format."""
    extra = extra_config or {}
    config = {"template": {domain: config, **trigger, **extra}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


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


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


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
