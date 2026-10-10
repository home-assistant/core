"""The tests for the Netatmo climate platform."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

from pyatmo.room import Room
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
from homeassistant.helpers import entity_registry as er

from .common import (
    HOME_ID,
    fake_post_request,
    selected_platforms,
    simulate_webhook,
    snapshot_platform_entities,
)

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
    select_entity = "select.myhome_schedule"

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


class _ClimateLastFeatures(set[str]):
    """Room features iterating with the climate feature last."""

    def __iter__(self) -> Iterator[str]:
        """Iterate over the features with climate last."""
        return iter(
            sorted(super().__iter__(), key=lambda feature: feature == "climate")
        )


class _ClimateLastRoom(Room):
    """Netatmo room iterating over its features with climate last.

    pyatmo keeps the room features in a set, so their iteration order
    changes with the hash seed of the process.
    """

    def evaluate_device_type(self) -> None:
        """Evaluate the device type keeping the features ordered."""
        self.features = _ClimateLastFeatures(self.features)
        super().evaluate_device_type()


async def test_select_created_when_climate_is_not_first_room_feature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the schedule select does not depend on the room features order.

    Simulate a home whose only climate room has a Smarther (BNS), which also
    reports humidity, with the climate feature iterated last.
    """

    def keep_only_smarther_climate_room(payload: dict[str, Any]) -> None:
        body = payload.get("body")
        if not isinstance(body, dict):
            return
        for home in body.get("homes", []):
            if home["id"] != HOME_ID:
                continue
            module_types = {module["id"]: module["type"] for module in home["modules"]}
            for room in home["rooms"]:
                room["module_ids"] = [
                    module_id
                    for module_id in room.get("module_ids", [])
                    if module_types[module_id] not in {"NATherm1", "NRV", "OTH", "OTM"}
                ]

    async def fake_post(*args: Any, **kwargs: Any):
        return await fake_post_request(
            hass, *args, msg_callback=keep_only_smarther_climate_room, **kwargs
        )

    with (
        selected_platforms([Platform.SELECT]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("pyatmo.home.Room", _ClimateLastRoom),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("select.myhome_schedule").state == "Default"
