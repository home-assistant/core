"""Test the Hi-Link HLK-SW16 setup."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hlk_sw16.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir, translation
from homeassistant.setup import async_setup_component

from . import create_mock_hlk_sw16_connection

YAML_CONFIG = {
    DOMAIN: {
        "device1": {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 8080,
            "switches": {0: {"name": "Relay 0"}},
        }
    }
}


@pytest.mark.parametrize(
    ("existing_host", "entry_count"),
    [
        pytest.param("192.168.1.2", 2, id="imported"),
        pytest.param("127.0.0.1", 1, id="already_configured"),
    ],
)
async def test_import_creates_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    existing_host: str,
    entry_count: int,
) -> None:
    """Test importing YAML creates the deprecation issue."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: existing_host, CONF_PORT: 8080}
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            return_value=await create_mock_hlk_sw16_connection(False),
        ),
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == entry_count
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Hi-Link HLK-SW16",
    }
    assert len(issue_registry.issues) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [pytest.param(TimeoutError, "cannot_connect", id="cannot_connect")],
)
async def test_import_abort_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test a failed YAML import creates an issue for the abort reason."""
    with patch(
        "homeassistant.components.hlk_sw16.config_flow.connect_client",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Hi-Link HLK-SW16",
    }
    assert len(issue_registry.issues) == 1


async def test_import_partial_failure_keeps_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed device import prevents the remove-your-YAML issue."""
    client = await create_mock_hlk_sw16_connection(False)

    async def connect(hass: HomeAssistant, user_input: dict[str, Any]) -> object:
        if user_input[CONF_HOST] == "127.0.0.2":
            raise TimeoutError
        return client

    config = {
        DOMAIN: {
            **YAML_CONFIG[DOMAIN],
            "device2": {
                CONF_HOST: "127.0.0.2",
                CONF_PORT: 8080,
                "switches": {0: {"name": "Relay 0"}},
            },
        }
    }
    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            side_effect=connect,
        ),
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert len(issue_registry.issues) == 1


async def test_import_finishes_before_setup_returns(hass: HomeAssistant) -> None:
    """Test all YAML devices are imported before the integration setup returns."""
    await translation.async_load_integrations(hass, {DOMAIN})
    config = {
        DOMAIN: {
            **YAML_CONFIG[DOMAIN],
            "device2": {
                CONF_HOST: "127.0.0.2",
                CONF_PORT: 8080,
                "switches": {0: {"name": "Relay 0"}},
            },
        }
    }
    with (
        patch(
            "homeassistant.components.hlk_sw16.config_flow.connect_client",
            return_value=await create_mock_hlk_sw16_connection(False),
        ),
        patch(
            "homeassistant.components.hlk_sw16.async_setup_entry",
            return_value=None,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)

        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
