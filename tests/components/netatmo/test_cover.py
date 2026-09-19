"""The tests for Netatmo cover."""

from datetime import timedelta
import math
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverEntityFeature,
)
from homeassistant.components.netatmo.coordinator import (
    CLOUD_FACTOR,
    DEFAULT_INTERVALS,
    HOME,
    SCAN_INTERVAL,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, snapshot_platform_entities

from tests.common import MockConfigEntry, async_fire_time_changed

# The mocked config entry uses the "cloud" auth implementation, so the
# coordinator polls HOME every DEFAULT_INTERVALS[HOME] / CLOUD_FACTOR
# seconds. Tick at half the coordinator's own polling cadence and past
# that interval with margin, so this keeps working if any of these
# constants change.
POLL_TICK = timedelta(seconds=SCAN_INTERVAL / 2)
POLL_TICKS = (
    math.ceil(DEFAULT_INTERVALS[HOME] / CLOUD_FACTOR / POLL_TICK.total_seconds()) + 2
)


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
        Platform.COVER,
        entity_registry,
        snapshot,
    )


@pytest.mark.parametrize(
    ("cover_entity", "module_id"),
    [
        ("cover.entrance_blinds", "0009999992"),
        ("cover.bubendorff_blind", "0009999993"),
    ],
    ids=["nbr", "nbo"],
)
async def test_position_reporting_cover_setup_and_services(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    cover_entity: str,
    module_id: str,
) -> None:
    """Test setup and services for covers that report a real position."""
    with selected_platforms([Platform.COVER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    assert (state := hass.states.get(cover_entity))
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0
    assert state.attributes["supported_features"] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    # Test cover open
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": module_id,
                        "target_position": 100,
                        "bridge": "12:34:56:30:d5:d4",
                    }
                ]
            }
        )
    assert hass.states.get(cover_entity).state == "open"

    # Test cover close
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": module_id,
                        "target_position": 0,
                        "bridge": "12:34:56:30:d5:d4",
                    }
                ]
            }
        )
    assert hass.states.get(cover_entity).state == "closed"

    # Test stop cover
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": module_id,
                        "target_position": -1,
                        "bridge": "12:34:56:30:d5:d4",
                    }
                ]
            }
        )

    # Test set cover position
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: cover_entity, ATTR_POSITION: 50},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": module_id,
                        "target_position": 50,
                        "bridge": "12:34:56:30:d5:d4",
                    }
                ]
            }
        )


async def test_movement_only_cover_setup_and_services(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test setup and services for a cover that only reports movement direction."""
    with selected_platforms([Platform.COVER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    cover_entity = "cover.mhs1_shutter"

    assert (state := hass.states.get(cover_entity))
    assert state.state == "unknown"
    assert state.attributes["supported_features"] == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert "current_position" not in state.attributes

    # Test cover open
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "0009999994",
                        "target_position": 100,
                        "bridge": "12:34:56:40:d5:d4",
                    }
                ]
            }
        )
    assert hass.states.get(cover_entity).state == "opening"

    # Test cover close
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "0009999994",
                        "target_position": 0,
                        "bridge": "12:34:56:40:d5:d4",
                    }
                ]
            }
        )
    assert hass.states.get(cover_entity).state == "closing"

    # Stop always resets to unknown; the actor does not resume reporting a
    # direction or position.
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "0009999994",
                        "target_position": -1,
                        "bridge": "12:34:56:40:d5:d4",
                    }
                ]
            }
        )
    assert hass.states.get(cover_entity).state == "unknown"

    # Setting an exact position is not supported by this module.
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: cover_entity, ATTR_POSITION: 50},
            blocking=True,
        )


class _Mhs1TargetPositionOverride:
    """Patch homestatus payloads to report a test-controlled target_position.

    Passed to the netatmo_auth fixture via indirect parametrization, so the
    mock wiring stays in one place; the test drives the polled value by
    mutating `.value` between poll cycles.
    """

    def __init__(self, module_id: str, value: int) -> None:
        """Initialize with the module to patch and its initial value."""
        self.module_id = module_id
        self.value = value

    def __call__(self, payload: dict[str, Any]) -> None:
        """Apply the current value to the matching module in the payload."""
        home = payload.get("body", {}).get("home", {})
        for module in home.get("modules", []):
            if module.get("id") == self.module_id:
                module["target_position"] = self.value


MHS1_TARGET_POSITION_OVERRIDE = _Mhs1TargetPositionOverride("0009999994", 50)


@pytest.mark.parametrize("netatmo_auth", [MHS1_TARGET_POSITION_OVERRIDE], indirect=True)
async def test_movement_only_cover_tracks_polled_target_position(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a polled update re-derives movement direction correctly.

    target_position reflects whether the actor is still driving the motor,
    reverting to 50 only once its own configured drive duration elapses -
    potentially well after the shutter physically stopped. Polled updates
    must keep is_opening/is_closing in sync with it, including reverting to
    "unknown" once the actor stops driving, even without an explicit stop
    command.
    """
    cover_entity = "cover.mhs1_shutter"
    MHS1_TARGET_POSITION_OVERRIDE.value = 50

    with selected_platforms([Platform.COVER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        with patch("pyatmo.home.Home.async_set_state"):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_CLOSE_COVER,
                {ATTR_ENTITY_ID: cover_entity},
                blocking=True,
            )
        assert (state := hass.states.get(cover_entity))
        assert state.state == "closing"

        # Poll while the actor is still driving the motor (target_position
        # still 0) - the state must not change.
        MHS1_TARGET_POSITION_OVERRIDE.value = 0
        for _ in range(POLL_TICKS):
            freezer.tick(POLL_TICK)
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

        assert (state := hass.states.get(cover_entity))
        assert state.state == "closing"

        # Poll after the actor's configured drive duration has elapsed and
        # it has reverted target_position to 50 on its own - the entity
        # must follow, without needing an explicit stop command.
        MHS1_TARGET_POSITION_OVERRIDE.value = 50
        for _ in range(POLL_TICKS):
            freezer.tick(POLL_TICK)
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

        assert (state := hass.states.get(cover_entity))
        assert state.state == "unknown"
