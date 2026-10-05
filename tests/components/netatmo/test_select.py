"""The tests for the Netatmo climate platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    fake_post_request,
    selected_platforms,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
    select_entity = "select.myhome_schedule"

    # The home is in cooling mode, so only cooling schedules are offered
    assert hass.states.get(select_entity).state == "Default"
    assert hass.states.get(select_entity).attributes[ATTR_OPTIONS] == ["Default"]

    # Fake backend response changing the heating schedule
    response = {
        "event_type": "schedule",
        "schedule_id": "b1b54a2f45795764f59d50d8",
        "previous_schedule_id": "59d32176d183948b05ab4dce",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(select_entity).state == "Default"

    # A heating schedule cannot be selected while cooling
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: select_entity,
                ATTR_OPTION: "Winter",
            },
            blocking=True,
        )

    # Test setting a schedule
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


async def test_select_schedule_follows_temperature_control_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the offered schedules follow a change of temperature control mode."""
    heating = False

    def set_heating_mode(payload: dict[str, Any]) -> None:
        """Put the home in heating mode with the heating schedule selected."""
        if not heating:
            return
        for home in payload.get("body", {}).get("homes", []):
            if home["id"] != "91763b24c43d3e344f424e8b":
                continue
            home["temperature_control_mode"] = "heating"
            for schedule in home["schedules"]:
                schedule["selected"] = schedule["id"] == "b1b54a2f45795764f59d50d8"

    async def fake_post(*args: Any, **kwargs: Any):
        """Return backend data, in heating mode once switched."""
        return await fake_post_request(
            hass, *args, msg_callback=set_heating_mode, **kwargs
        )

    with (
        selected_platforms(["climate", "select"]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        select_entity = "select.myhome_schedule"
        assert hass.states.get(select_entity).state == "Default"
        assert hass.states.get(select_entity).attributes[ATTR_OPTIONS] == ["Default"]

        # The home switches from cooling to heating in the backend
        heating = True
        freezer.tick(timedelta(hours=3))
        for _ in range(5):
            freezer.tick(timedelta(minutes=5))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(select_entity).state == "Winter"
    assert hass.states.get(select_entity).attributes[ATTR_OPTIONS] == ["Winter"]

    with patch("pyatmo.home.Home.async_switch_schedule") as mock_switch_home_schedule:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: select_entity,
                ATTR_OPTION: "Winter",
            },
            blocking=True,
        )
        mock_switch_home_schedule.assert_called_once_with(
            schedule_id="b1b54a2f45795764f59d50d8"
        )


async def test_select_schedule_unknown_schedule_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test webhook with unknown schedule_id is silently ignored."""
    with selected_platforms(["climate", "select"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    select_entity = "select.myhome_schedule"
    original_state = hass.states.get(select_entity).state

    response = {
        "event_type": "schedule",
        "schedule_id": "unknown000000000000000000",
        "previous_schedule_id": "591b54a2764ff4d50d8b5795",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(select_entity).state == original_state
