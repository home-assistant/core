"""Linksys Smart Wi-Fi device tracker platform tests."""

from unittest.mock import AsyncMock, patch

from jnap import JNAPClient, JNAPDevice
import pytest

from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.components.linksys_smart.coordinator import (
    LinksysDataUpdateCoordinator,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

LAPTOP = JNAPDevice(
    mac="aa:bb:cc:dd:ee:ff",
    name="My Laptop",
    ip_address="192.168.1.10",
    hostname="my-laptop",
)
PHONE = JNAPDevice(
    mac="11:22:33:44:55:66",
    name="My Phone",
    ip_address="192.168.1.11",
    hostname="my-phone",
)


def _make_coordinator(
    hass: HomeAssistant,
    devices: dict[str, JNAPDevice],
    entry: MockConfigEntry | None = None,
) -> LinksysDataUpdateCoordinator:
    if entry is None:
        entry = MockConfigEntry(domain=DOMAIN)
    coordinator = LinksysDataUpdateCoordinator(hass, entry, AsyncMock(spec=JNAPClient))
    coordinator.data = devices
    return coordinator


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    coordinator: LinksysDataUpdateCoordinator,
) -> None:
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.linksys_smart.async_get_clientsession",
            return_value=object(),
        ),
        patch("homeassistant.components.linksys_smart.JNAPClient"),
        patch(
            "homeassistant.components.linksys_smart.LinksysDataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_when_connected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity state and attributes when device is connected."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    coordinator = _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}, entry)
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)
    await _setup_entry(hass, entry, coordinator)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, "aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.unique_id == "aa:bb:cc:dd:ee:ff"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "home"
    assert state.attributes["source_type"] == "router"
    assert state.attributes["ip"] == "192.168.1.10"
    assert state.attributes["host_name"] == "my-laptop"
    assert state.attributes["mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_when_disconnected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity state when device is not present in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    coordinator = _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}, entry)
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)
    await _setup_entry(hass, entry, coordinator)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    coordinator.data = {}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, "aa:bb:cc:dd:ee:ff"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "not_home"
    assert "ip" not in state.attributes
    assert "host_name" not in state.attributes


async def test_setup_entry_creates_entity_per_device(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test async_setup_entry adds one entity per device in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    coordinator = _make_coordinator(
        hass,
        {"aa:bb:cc:dd:ee:ff": LAPTOP, "11:22:33:44:55:66": PHONE},
        entry,
    )
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)

    await _setup_entry(hass, entry, coordinator)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 2
    assert {entity.unique_id for entity in entries} == {
        "aa:bb:cc:dd:ee:ff",
        "11:22:33:44:55:66",
    }


async def test_setup_entry_does_not_duplicate_on_coordinator_update(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that existing devices are not re-added when coordinator refreshes."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    coordinator = _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}, entry)
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)

    await _setup_entry(hass, entry, coordinator)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1

    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1


async def test_new_device_added_on_coordinator_update(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a new entity is added when a new device appears in coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    coordinator = _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}, entry)
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)

    await _setup_entry(hass, entry, coordinator)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1

    coordinator.data = {"aa:bb:cc:dd:ee:ff": LAPTOP, "11:22:33:44:55:66": PHONE}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 2
    assert {entity.unique_id for entity in entries} == {
        "aa:bb:cc:dd:ee:ff",
        "11:22:33:44:55:66",
    }


async def test_yaml_config_no_entry_creates_credentials_required_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML config without a config entry creates a credentials-required issue."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "linksys_smart",
                "host": "192.168.1.1",
            }
        },
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_credentials_required"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
        "host": "192.168.1.1",
    }


async def test_yaml_config_with_entry_creates_remove_yaml_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML config with an existing config entry prompts removal of YAML."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "linksys_smart",
                "host": "192.168.1.1",
            }
        },
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Linksys Smart Wi-Fi",
    }
