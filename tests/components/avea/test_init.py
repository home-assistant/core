"""Tests for the Avea integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.avea.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_setup_entry_retries_when_ble_device_is_missing(
    hass: HomeAssistant,
) -> None:
    """Test setup retries when the Bluetooth device is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom",
        unique_id=AVEA_DISCOVERY_INFO.address,
        data={CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.avea.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_import_creates_entries_for_discovered_bulbs(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates entries for each discovered bulb."""
    bulb_one = MagicMock()
    bulb_one.addr = "AA:BB:CC:DD:EE:FF"
    bulb_one.get_name.return_value = "Bedroom"
    bulb_one.get_brightness.return_value = 0

    bulb_two = MagicMock()
    bulb_two.addr = "11:22:33:44:55:66"
    bulb_two.get_name.return_value = "Desk"
    bulb_two.get_brightness.return_value = 0

    with (
        patch(
            "homeassistant.components.avea.light.avea.discover_avea_bulbs",
            return_value=[bulb_one, bulb_two],
        ),
        patch(
            "homeassistant.components.avea.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_component(
            hass, "light", {"light": {"platform": DOMAIN}}
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {(entry.unique_id, entry.title) for entry in entries} == {
        ("AA:BB:CC:DD:EE:FF", "Bedroom"),
        ("11:22:33:44:55:66", "Desk"),
    }

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_import_skips_bulbs_that_fail_validation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import skips bulbs that fail validation."""
    failing_bulb = MagicMock()
    failing_bulb.addr = "AA:BB:CC:DD:EE:FF"
    failing_bulb.get_name.side_effect = RuntimeError

    valid_bulb = MagicMock()
    valid_bulb.addr = "11:22:33:44:55:66"
    valid_bulb.get_name.return_value = "Desk"
    valid_bulb.get_brightness.return_value = 0

    with (
        patch(
            "homeassistant.components.avea.light.avea.discover_avea_bulbs",
            return_value=[failing_bulb, valid_bulb],
        ),
        patch(
            "homeassistant.components.avea.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_component(
            hass, "light", {"light": {"platform": DOMAIN}}
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "11:22:33:44:55:66"
    assert entries[0].title == "Desk"

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_import_handles_when_no_bulbs_are_discovered(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import completes when no bulbs can be discovered."""
    with patch(
        "homeassistant.components.avea.light.avea.discover_avea_bulbs",
        return_value=[],
    ):
        assert await async_setup_component(
            hass, "light", {"light": {"platform": DOMAIN}}
        )
        await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_yaml_import_handles_when_all_bulbs_fail_validation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import completes when all bulbs fail validation."""
    failing_bulb = MagicMock()
    failing_bulb.addr = "AA:BB:CC:DD:EE:FF"
    failing_bulb.get_name.side_effect = RuntimeError

    with patch(
        "homeassistant.components.avea.light.avea.discover_avea_bulbs",
        return_value=[failing_bulb],
    ):
        assert await async_setup_component(
            hass, "light", {"light": {"platform": DOMAIN}}
        )
        await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
