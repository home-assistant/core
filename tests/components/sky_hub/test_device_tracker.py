"""Tests for Sky Hub device trackers."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.sky_hub.const import DEFAULT_HOST, DOMAIN
from homeassistant.components.sky_hub.device_tracker import async_setup_scanner
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import LAPTOP, PHONE, MockDevice


def _yaml_import_issue_id(host: str) -> str:
    """Return the YAML import issue ID for a host."""
    return f"yaml_import_cannot_connect_{host}"


@pytest.mark.usefixtures("mock_router")
async def test_legacy_setup(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML setup imports a config entry and reports deprecation."""
    await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": {"platform": DOMAIN, CONF_HOST: DEFAULT_HOST}},
    )

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == {CONF_HOST: DEFAULT_HOST}

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_yaml"


async def test_legacy_setup_cannot_connect(
    hass: HomeAssistant,
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test failed YAML imports report an issue."""
    mock_router.success_init = False

    await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": {"platform": DOMAIN, CONF_HOST: DEFAULT_HOST}},
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(DOMAIN, _yaml_import_issue_id(DEFAULT_HOST))
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": DEFAULT_HOST}


async def test_legacy_setup_clears_connection_issue(
    hass: HomeAssistant,
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful YAML import clears an earlier connection issue."""
    mock_router.success_init = False
    await async_setup_scanner(hass, {CONF_HOST: DEFAULT_HOST}, AsyncMock())
    assert (
        issue_registry.async_get_issue(DOMAIN, _yaml_import_issue_id(DEFAULT_HOST))
        is not None
    )

    mock_router.success_init = True
    await async_setup_scanner(hass, {CONF_HOST: DEFAULT_HOST}, AsyncMock())
    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(DOMAIN, _yaml_import_issue_id(DEFAULT_HOST))
        is None
    )


async def test_legacy_setup_connection_issues_are_host_specific(
    hass: HomeAssistant,
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test connection issues are tracked independently per YAML host."""
    other_host = "192.168.0.1"

    mock_router.success_init = False
    await async_setup_scanner(hass, {CONF_HOST: DEFAULT_HOST}, AsyncMock())
    await async_setup_scanner(hass, {CONF_HOST: other_host}, AsyncMock())

    issue_default = issue_registry.async_get_issue(
        DOMAIN, _yaml_import_issue_id(DEFAULT_HOST)
    )
    issue_other = issue_registry.async_get_issue(
        DOMAIN, _yaml_import_issue_id(other_host)
    )

    assert issue_default is not None
    assert issue_default.translation_placeholders == {"host": DEFAULT_HOST}
    assert issue_other is not None
    assert issue_other.translation_placeholders == {"host": other_host}


async def test_legacy_setup_success_only_clears_matching_host_issue(
    hass: HomeAssistant,
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test success for one host does not clear another host's issue."""
    other_host = "192.168.0.1"

    mock_router.success_init = False
    await async_setup_scanner(hass, {CONF_HOST: DEFAULT_HOST}, AsyncMock())
    await async_setup_scanner(hass, {CONF_HOST: other_host}, AsyncMock())

    mock_router.success_init = True
    await async_setup_scanner(hass, {CONF_HOST: DEFAULT_HOST}, AsyncMock())
    await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _yaml_import_issue_id(DEFAULT_HOST))
        is None
    )
    assert (
        issue_registry.async_get_issue(DOMAIN, _yaml_import_issue_id(other_host))
        is not None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_router")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test initial devices create tracker entities with names and identifiers."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.laptop")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["host_name"] == LAPTOP.name
    assert state.attributes["mac"] == LAPTOP.mac

    registry_entry = entity_registry.async_get("device_tracker.laptop")
    assert registry_entry is not None
    assert registry_entry.unique_id == f"{mock_config_entry.entry_id}_{LAPTOP.mac}"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_new_device_discovered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test devices discovered during polling create new tracker entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.laptop").state == STATE_HOME
    assert hass.states.get("device_tracker.phone") is None
    assert len(hass.states.async_all("device_tracker")) == 1

    mock_router.async_get_skyhub_data.return_value = [LAPTOP, PHONE]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("device_tracker.laptop").state == STATE_HOME
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert len(hass.states.async_all("device_tracker")) == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test devices missing from a successful scan become not home."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.laptop").state == STATE_HOME

    mock_router.async_get_skyhub_data.return_value = [PHONE]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("device_tracker.laptop").state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_scan_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed scan makes existing tracker entities unavailable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_router.async_get_skyhub_data.return_value = None
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("device_tracker.laptop").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("new_name", "expected_host_name", "expected_device_name"),
    [
        pytest.param("Work laptop", "Work laptop", "Work laptop", id="renamed"),
        # The device keeps its name instead of falling back to the MAC address
        pytest.param("", None, LAPTOP.name, id="name_removed"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_name_updated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    new_name: str,
    expected_host_name: str | None,
    expected_device_name: str,
) -> None:
    """Test a device name change updates the existing tracker entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_router.async_get_skyhub_data.return_value = [MockDevice(LAPTOP.mac, new_name)]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("device_tracker.laptop")
    assert state.state == STATE_HOME
    assert state.attributes.get("host_name") == expected_host_name
    assert state.attributes["friendly_name"] == expected_device_name
    assert len(hass.states.async_all("device_tracker")) == 1

    registry_entry = entity_registry.async_get("device_tracker.laptop")
    assert registry_entry is not None
    device = device_registry.async_get(registry_entry.device_id)
    assert device is not None
    assert device.name == expected_device_name
