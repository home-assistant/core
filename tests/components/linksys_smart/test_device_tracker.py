"""Linksys Smart Wi-Fi device tracker platform tests."""

from unittest.mock import AsyncMock, patch

from jnap import JNAPClient, JNAPDevice
import pytest

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.components.linksys_smart.coordinator import (
    LinksysDataUpdateCoordinator,
)
from homeassistant.components.linksys_smart.device_tracker import LinksysScannerEntity
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


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({"aa:bb:cc:dd:ee:ff": LAPTOP}, True, id="connected"),
        pytest.param({}, False, id="not_connected"),
    ],
)
async def test_entity_is_connected(
    hass: HomeAssistant,
    data: dict[str, JNAPDevice],
    expected: bool,
) -> None:
    """Test is_connected reflects whether the device MAC is in current coordinator data."""
    entity = LinksysScannerEntity(_make_coordinator(hass, data), LAPTOP)
    assert entity.is_connected is expected


async def test_entity_mac_address(hass: HomeAssistant) -> None:
    """Test mac_address returns the device MAC."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.mac_address == "aa:bb:cc:dd:ee:ff"


async def test_entity_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id is the device MAC address."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_entity_name(hass: HomeAssistant) -> None:
    """Test name is taken from the device."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.name == "My Laptop"


async def test_entity_source_type(hass: HomeAssistant) -> None:
    """Test source_type is ROUTER."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.source_type is SourceType.ROUTER


async def test_entity_ip_address_when_connected(hass: HomeAssistant) -> None:
    """Test ip_address is read from coordinator data when the device is connected."""
    entity = LinksysScannerEntity(
        _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}), LAPTOP
    )
    assert entity.ip_address == "192.168.1.10"


async def test_entity_ip_address_when_disconnected(hass: HomeAssistant) -> None:
    """Test ip_address is None when the device is not in coordinator data."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.ip_address is None


async def test_entity_hostname_when_connected(hass: HomeAssistant) -> None:
    """Test hostname is read from coordinator data when the device is connected."""
    entity = LinksysScannerEntity(
        _make_coordinator(hass, {"aa:bb:cc:dd:ee:ff": LAPTOP}), LAPTOP
    )
    assert entity.hostname == "my-laptop"


async def test_entity_hostname_when_disconnected(hass: HomeAssistant) -> None:
    """Test hostname is None when the device is not in coordinator data."""
    entity = LinksysScannerEntity(_make_coordinator(hass, {}), LAPTOP)
    assert entity.hostname is None


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
