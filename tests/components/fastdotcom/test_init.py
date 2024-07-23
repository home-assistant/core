"""Test for Sensibo component Init."""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=5.0
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_from_import(hass: HomeAssistant) -> None:
    """Test imported entry."""
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=5.0
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {"fastdotcom": {}},
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "5.0"


async def test_delayed_speedtest_during_startup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test delayed speedtest during startup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    original_state = hass.state
    hass.set_state(CoreState.starting)
    with patch("homeassistant.components.fastdotcom.coordinator.fast_com"):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    hass.set_state(original_state)

    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.fast_com_download")
    # Assert state is Unknown as fast.com isn't starting until HA has started
    assert state.state is STATE_UNKNOWN

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=5.0
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "5.0"

    assert config_entry.state is ConfigEntryState.LOADED


async def test_service_deprecated(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test deprecated service."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=5.0
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN,
        "speedtest",
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "service_deprecation")
    assert issue
    assert issue.is_fixable is True
    assert issue.translation_key == "service_deprecation"
