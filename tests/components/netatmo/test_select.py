"""The tests for the Netatmo climate platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.netatmo.const import DATA_SCHEDULES, DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_WEBHOOK_ID,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, simulate_webhook, snapshot_platform_entities

from tests.common import MockConfigEntry


async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.SELECT,
        entity_registry,
        snapshot,
    )


async def test_select_schedule_thermostats(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    netatmo_auth: AsyncMock,
) -> None:
    """Test service for selecting Netatmo schedule with thermostats."""
    with selected_platforms(["climate", "select"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    select_entity = "select.myhome"

    assert hass.states.get(select_entity).state == "Default"

    # Fake backend response changing schedule
    response = {
        "event_type": "schedule",
        "schedule_id": "b1b54a2f45795764f59d50d8",
        "previous_schedule_id": "59d32176d183948b05ab4dce",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(select_entity).state == "Winter"
    assert hass.states.get(select_entity).attributes[ATTR_OPTIONS] == [
        "Default",
        "Winter",
    ]

    # Test setting a different schedule
    with patch("pyatmo.home.Home.async_switch_schedule") as mock_switch_home_schedule:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: select_entity,
                ATTR_OPTION: "Default",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_home_schedule.assert_called_once_with(
            schedule_id="591b54a2764ff4d50d8b5795"
        )

    # Fake backend response changing schedule
    response = {
        "event_type": "schedule",
        "schedule_id": "591b54a2764ff4d50d8b5795",
        "previous_schedule_id": "b1b54a2f45795764f59d50d8",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(select_entity).state == "Default"


async def test_select_schedule_optimistic_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test that selecting a schedule updates state immediately without waiting for a webhook."""
    with selected_platforms(["climate", "select"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    select_entity = "select.myhome"
    assert hass.states.get(select_entity).state == "Default"

    with patch("pyatmo.home.Home.async_switch_schedule"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: select_entity, ATTR_OPTION: "Winter"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # State must update immediately (optimistic), without waiting for webhook or API poll
    assert hass.states.get(select_entity).state == "Winter"


async def test_select_schedule_updates_climate_attribute(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test that selecting a schedule updates climate selected_schedule attribute via internal signal."""
    with selected_platforms(["climate", "select"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    climate_entity = "climate.livingroom"
    select_entity = "select.myhome"
    assert hass.states.get(select_entity).state == "Default"

    with patch("pyatmo.home.Home.async_switch_schedule"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: select_entity, ATTR_OPTION: "Winter"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Climate entity must reflect the new schedule immediately via SIGNAL_SCHEDULE_CHANGED
    assert hass.states.get(climate_entity).attributes["selected_schedule"] == "Winter"
    assert (
        hass.states.get(climate_entity).attributes["selected_schedule_id"]
        == "b1b54a2f45795764f59d50d8"
    )


async def test_select_schedule_invalid_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    netatmo_auth: AsyncMock,
) -> None:
    """Test that selecting a schedule not found in DATA_SCHEDULES logs an error."""
    with selected_platforms(["climate", "select"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    select_entity = "select.myhome"
    assert hass.states.get(select_entity).state == "Default"

    # Clear the schedule cache so the option lookup fails while HA still accepts the call
    home_id = "91763b24c43d3e344f424e8b"
    original_schedules = hass.data[DOMAIN][DATA_SCHEDULES].get(home_id, {}).copy()
    hass.data[DOMAIN][DATA_SCHEDULES][home_id] = {}

    with patch("pyatmo.home.Home.async_switch_schedule") as mock_switch_schedule:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: select_entity, ATTR_OPTION: "Default"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_schedule.assert_not_called()

    assert "Default is not a valid schedule" in caplog.text

    # Restore schedule cache
    hass.data[DOMAIN][DATA_SCHEDULES][home_id] = original_schedules
