"""Tests for UniFi AP Direct device tracker."""

from unifi_ap import UniFiAPConnectionException

from homeassistant import config_entries
from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_unifiap,
    entity_registry: EntityRegistry,
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity registry should contain the device_tracker entities created by the integration
    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "unifi_direct"
    ]
    assert len(entries) == 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entity_id.startswith("device_tracker.my_phone") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.my_laptop") for entity_id in entity_ids
    )


async def test_device_tracker_deduplicates_multiple_ap_clients(
    hass: HomeAssistant,
    mock_unifiap,
    entity_registry: EntityRegistry,
) -> None:
    """Test multiple APs from one entry create a single entity per client MAC."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="UniFi AP (192.168.1.2, 192.168.1.3)",
        data={
            CONF_HOSTS: [
                {
                    CONF_HOST: "192.168.1.2",
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password",
                    CONF_PORT: 22,
                },
                {
                    CONF_HOST: "192.168.1.3",
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password",
                    CONF_PORT: 22,
                },
            ]
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "unifi_direct"
    ]
    assert len(entries) == 3

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entry_id.startswith("device_tracker.my_phone") for entry_id in entity_ids
    )
    assert any(
        entry_id.startswith("device_tracker.my_laptop") for entry_id in entity_ids
    )
    assert any(
        entry_id.startswith("device_tracker.my_desktop") for entry_id in entity_ids
    )


async def test_setup_scanner_legacy_platform_imports_config_entry(
    hass: HomeAssistant,
    mock_unifiap,
) -> None:
    """Test legacy device tracker setup triggers config flow import."""
    config = {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_PORT: 22,
    }

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **config}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            }
        ]
    }
    assert entries[0].source == config_entries.SOURCE_IMPORT


async def test_setup_scanner_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant, mock_unifiap, issue_registry: IssueRegistry
) -> None:
    """Test that issue is created when legacy device tracker setup cannot connect."""
    config = {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_PORT: 22,
    }

    mock_unifiap._set_get_clients_side_effect(UniFiAPConnectionException("fail"))

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **config}]},
    )
    await hass.async_block_till_done()

    # Verify the issue was created in the registry
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")

    assert len(issue_registry.issues) == 1
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": "192.168.1.2"}
