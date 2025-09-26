"""The test for the HERE Travel Time integration."""

from datetime import datetime

import pytest

from homeassistant.components.here_travel_time.config_flow import (
    DEFAULT_OPTIONS,
    HERETravelTimeConfigFlow,
)
from homeassistant.components.here_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DOMAIN,
    ROUTE_MODE_FASTEST,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DEFAULT_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("valid_response")
@pytest.mark.parametrize(
    "options",
    [
        DEFAULT_OPTIONS,
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_DEPARTURE_TIME: datetime.now(),
        },
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: datetime.now(),
        },
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        },
    ],
)
async def test_unload_entry(hass: HomeAssistant, options) -> None:
    """Test that unloading an entry works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data=DEFAULT_CONFIG,
        options=options,
        version=HERETravelTimeConfigFlow.VERSION,
        minor_version=HERETravelTimeConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("valid_response")
async def test_migrate_entry_v1_1_v1_2(
    hass: HomeAssistant,
) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_CONFIG,
        options=DEFAULT_OPTIONS,
        version=1,
        minor_version=1,
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.minor_version == 2
    assert updated_entry.options[CONF_TRAFFIC_MODE] is True


@pytest.mark.usefixtures("valid_response")
async def test_issue_multiple_here_integrations_detected(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that an issue is created when multiple HERE integrations are detected."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234567890",
        data=DEFAULT_CONFIG,
        options=DEFAULT_OPTIONS,
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0987654321",
        data=DEFAULT_CONFIG,
        options=DEFAULT_OPTIONS,
    )
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
