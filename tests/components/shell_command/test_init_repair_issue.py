"""Test repair issue for reserved reload name."""

import pytest

from homeassistant.components import shell_command
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.mark.asyncio
async def test_repair_issue_on_reserved_reload_name(hass: HomeAssistant) -> None:
    """Test repair issue is created if 'reload' is used as a shell_command name."""
    config = {shell_command.DOMAIN: {"reload": "echo should not work"}}
    await async_setup_component(hass, shell_command.DOMAIN, config)
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(shell_command.DOMAIN, "reserved_reload")
    assert issue is not None
    assert issue.translation_key == "reserved_reload_name"
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.is_persistent
    assert issue.translation_placeholders["name"] == "reload"


@pytest.mark.asyncio
async def test_repair_issue_on_reload_service_reload(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test repair issue is created if 'reload' is used in YAML and reload service is called."""
    config = {shell_command.DOMAIN: {"test": "echo ok"}}
    await async_setup_component(hass, shell_command.DOMAIN, config)
    await hass.async_block_till_done()

    # Patch config load to return a config with 'reload' as a command
    async def _mock_async_hass_config_yaml(hass: HomeAssistant) -> dict:
        return {shell_command.DOMAIN: {"reload": "echo again"}}

    monkeypatch.setattr(
        "homeassistant.components.shell_command.conf_util.async_hass_config_yaml",
        _mock_async_hass_config_yaml,
    )
    await hass.services.async_call(
        shell_command.DOMAIN, shell_command.SERVICE_RELOAD, blocking=True
    )
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(shell_command.DOMAIN, "reserved_reload")
    assert issue is not None
    assert issue.translation_key == "reserved_reload_name"
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.is_persistent
    assert issue.translation_placeholders["name"] == "reload"
