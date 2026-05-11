"""Tests for the Avea integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.avea.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def _mock_discovered_bulb(
    address: str,
    name: str | None = None,
    brightness: int | None = 0,
    *,
    name_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a discovered Avea bulb for YAML import tests."""
    bulb = MagicMock()
    bulb.addr = address
    bulb.name = name or address
    if name_side_effect is not None:
        bulb.get_name.side_effect = name_side_effect
    else:
        bulb.get_name.return_value = name
    bulb.get_brightness.return_value = brightness
    return bulb


async def _setup_yaml_import(hass: HomeAssistant, bulbs: list[MagicMock]) -> None:
    """Set up the YAML import path with mocked discovered bulbs."""
    with (
        patch(
            "homeassistant.components.avea.light.avea.discover_avea_bulbs",
            return_value=bulbs,
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


async def test_setup_entry_retries_when_ble_device_is_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the Bluetooth device is unavailable."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.avea.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_import_creates_entries_for_discovered_bulbs(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates entries for each discovered bulb."""
    bulbs = [
        _mock_discovered_bulb("AA:BB:CC:DD:EE:FF", "Bedroom"),
        _mock_discovered_bulb("11:22:33:44:55:66", "Desk"),
    ]

    await _setup_yaml_import(hass, bulbs)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {(entry.unique_id, entry.title) for entry in entries} == {
        ("AA:BB:CC:DD:EE:FF", "Bedroom"),
        ("11:22:33:44:55:66", "Desk"),
    }
    for bulb in bulbs:
        bulb.close.assert_called_once()
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_skips_bulbs_that_fail_validation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import skips bulbs that fail validation."""
    bulbs = [
        _mock_discovered_bulb(
            "AA:BB:CC:DD:EE:FF",
            "Bedroom",
            name_side_effect=RuntimeError("boom"),
        ),
        _mock_discovered_bulb("11:22:33:44:55:66", "Desk"),
    ]

    await _setup_yaml_import(hass, bulbs)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "11:22:33:44:55:66"
    assert entries[0].title == "Desk"
    for bulb in bulbs:
        bulb.close.assert_called_once()
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_handles_when_no_bulbs_are_discovered(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import completes when no bulbs can be discovered."""
    await _setup_yaml_import(hass, [])

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_no_bulbs"
    )


async def test_yaml_import_handles_when_no_bulbs_can_be_imported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import completes when all bulbs fail validation."""
    bulbs = [
        _mock_discovered_bulb(
            "AA:BB:CC:DD:EE:FF",
            "Bedroom",
            name_side_effect=RuntimeError("boom"),
        )
    ]

    await _setup_yaml_import(hass, bulbs)

    assert hass.config_entries.async_entries(DOMAIN) == []
    bulbs[0].close.assert_called_once()
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_no_bulbs"
    )


async def test_yaml_import_ignores_unknown_bulb_name(hass: HomeAssistant) -> None:
    """Test YAML import ignores the library default name."""
    bulbs = [
        _mock_discovered_bulb(
            "AA:BB:CC:DD:EE:FF",
            "Unknown",
        )
    ]
    bulbs[0].name = "Bedroom"

    await _setup_yaml_import(hass, bulbs)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Bedroom"
