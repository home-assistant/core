"""Test the London Air init."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from pylondonair import LondonAirConnectionError, LondonAirData
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.london_air.const import CONF_LOCATIONS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_load_unload_entry(
    hass: HomeAssistant,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
    setup_entry: Callable[[list[str]], Awaitable[MockConfigEntry]],
) -> None:
    """Test loading and unloading the config entry."""
    mock_london_air_client.async_update.return_value = london_air_data

    entry = await setup_entry(["Merton"])
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.merton") is None


async def test_import_from_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test importing from YAML creates a config entry and a deprecation issue."""
    mock_london_air_client.async_update.return_value = london_air_data
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_LOCATIONS: ["Merton"]}

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_import_from_yaml_cannot_connect(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test a failed YAML import raises a specific issue instead of the migration notice."""
    mock_london_air_client.async_test_connection.side_effect = LondonAirConnectionError(
        "Request to London Air API failed"
    )
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}},
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN
