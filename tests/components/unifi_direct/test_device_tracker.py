"""Tests for UniFi AP Direct device tracker."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.unifi_direct import device_tracker
from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir


async def test_device_tracker_entities_created(
    hass: HomeAssistant, mock_config_entry, mock_unifiap
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity registry should contain the device_tracker entities created by the integration

    registry = er.async_get(hass)
    entries = [
        entry
        for entry in registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "unifi_direct"
    ]
    assert len(entries) >= 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entity_id.startswith("device_tracker.my_phone") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.my_laptop") for entity_id in entity_ids
    )


async def test_setup_scanner_legacy_platform_imports_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test legacy device tracker setup triggers config flow import."""
    config = {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_PORT: 22,
    }

    with patch.object(
        hass.config_entries.flow,
        "async_init",
        new=AsyncMock(
            return_value={"type": data_entry_flow.FlowResultType.CREATE_ENTRY}
        ),
    ) as mock_flow_init:
        assert await device_tracker.async_setup_scanner(hass, config, AsyncMock())

    mock_flow_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )


async def test_setup_scanner_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test that issue is created when legacy device tracker setup cannot connect."""
    config = {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_PORT: 22,
    }

    with patch.object(
        hass.config_entries.flow,
        "async_init",
        new=AsyncMock(
            return_value={
                "type": data_entry_flow.FlowResultType.ABORT,
                "reason": "cannot_connect",
            }
        ),
    ):
        assert await device_tracker.async_setup_scanner(hass, config, AsyncMock())

    # Verify the issue was created in the registry
    issue_registry_instance = ir.async_get(hass)
    issue = issue_registry_instance.async_get_issue(
        DOMAIN, "yaml_import_cannot_connect"
    )
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": "192.168.1.2"}
