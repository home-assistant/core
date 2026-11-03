"""Tests for the BT Home Hub 5 device tracker platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests

from homeassistant.components.bt_home_hub_5.const import (
    DEFAULT_HOST,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.bt_home_hub_5.device_tracker import async_setup_scanner
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PLATFORM, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

MOCK_HOST = "192.168.1.254"
MAC_1 = "00:11:22:33:44:55"
MAC_2 = "AA:BB:CC:DD:EE:FF"
DEVICE_1 = {MAC_1: "Phone"}
DEVICE_BOTH = {MAC_1: "Phone", MAC_2: "Laptop"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device tracker entities track connected status dynamically."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_1,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    state_phone = hass.states.get("device_tracker.phone")
    assert state_phone is not None
    assert state_phone.state == STATE_HOME

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_BOTH,
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state_laptop = hass.states.get("device_tracker.laptop")
    assert state_laptop is not None
    assert state_laptop.state == STATE_HOME

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value={MAC_2: "Laptop"},
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state_phone = hass.states.get("device_tracker.phone")
    assert state_phone is not None
    assert state_phone.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_without_name_falls_back_to_mac(hass: HomeAssistant) -> None:
    """Test a device with a blank router name is named after its MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value={MAC_1: ""},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.00_11_22_33_44_55")
    assert state is not None
    assert state.name == MAC_1
    assert "host_name" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_same_device_on_two_hubs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device seen by two hubs gets an entity under each hub."""
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: host},
            title=f"BT Home Hub 5 ({host})",
        )
        for host in (MOCK_HOST, "192.168.2.254")
    ]

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_1,
    ):
        for entry in entries:
            entry.add_to_hass(hass)
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    for entry in entries:
        assert entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, f"{entry.entry_id}_{MAC_1}"
        )


async def test_coordinator_update_failure(hass: HomeAssistant) -> None:
    """Test coordinator handles connection exceptions correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        side_effect=requests.exceptions.ConnectionError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_data_none(hass: HomeAssistant) -> None:
    """Test coordinator handles None return value from get_devicelist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_index_error(hass: HomeAssistant) -> None:
    """Test coordinator handles parsing IndexError correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        side_effect=IndexError("Payload parsing error"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_scanner_legacy(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test legacy YAML async_setup_scanner registers issue and creates import flow."""
    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_1,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_1,
        ),
    ):
        result = await async_setup_scanner(
            hass, {CONF_HOST: MOCK_HOST}, see=AsyncMock(), discovery_info=None
        )
        assert result is True
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_yaml"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(requests.exceptions.ConnectionError, id="cannot_connect"),
        pytest.param(IndexError, id="unknown"),
    ],
)
async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    side_effect: type[Exception],
) -> None:
    """Test a failed YAML import reports an error instead of a completed import."""
    with patch(
        "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
        side_effect=side_effect,
    ):
        result = await async_setup_scanner(
            hass, {CONF_HOST: MOCK_HOST}, see=AsyncMock(), discovery_info=None
        )
        await hass.async_block_till_done()

    assert result is True
    assert not hass.config_entries.async_entries(DOMAIN)
    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, f"yaml_import_cannot_connect_{MOCK_HOST}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "yaml_import_cannot_connect"


async def test_yaml_setup_uses_default_host(hass: HomeAssistant) -> None:
    """Test YAML configuration without a host imports the default address."""
    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_1,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_1,
        ),
    ):
        assert await async_setup_component(
            hass,
            DEVICE_TRACKER_DOMAIN,
            {DEVICE_TRACKER_DOMAIN: [{CONF_PLATFORM: DOMAIN}]},
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == DEFAULT_HOST


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_1,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
