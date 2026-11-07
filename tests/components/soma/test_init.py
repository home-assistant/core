"""Tests for the Soma integration setup and YAML import."""

from typing import Any
from unittest.mock import patch

from api.soma_api import SomaApi
import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests import RequestException

from homeassistant.components.soma import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

MOCK_HOST = "123.45.67.89"
MOCK_PORT = 3000
YAML_CONFIG = {DOMAIN: {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}}
SUCCESS_RESPONSE = {"result": "success", "shades": []}


async def test_import_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML configuration is imported and raises a deprecation issue."""
    with patch.object(SomaApi, "list_devices", return_value=SUCCESS_RESPONSE):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {"host": MOCK_HOST, "port": "3000"}
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Soma Connect",
    }


async def test_import_yaml_already_setup(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML configuration with an existing entry raises a deprecation issue."""
    MockConfigEntry(
        domain=DOMAIN, data={"host": MOCK_HOST, "port": MOCK_PORT}
    ).add_to_hass(hass)

    with patch.object(SomaApi, "list_devices", return_value=SUCCESS_RESPONSE):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("patch_kwargs", "reason"),
    [
        pytest.param(
            {"side_effect": RequestException()},
            "connection_error",
            id="request_exception",
        ),
        pytest.param({"return_value": {}}, "connection_error", id="key_error"),
        pytest.param(
            {"return_value": {"result": "error"}}, "result_error", id="result_error"
        ),
    ],
)
async def test_import_yaml_error(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    patch_kwargs: dict[str, Any],
    reason: str,
) -> None:
    """Test a failed YAML import raises an import issue."""
    with patch.object(SomaApi, "list_devices", **patch_kwargs):
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
        "integration_title": "Soma Connect",
    }
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
