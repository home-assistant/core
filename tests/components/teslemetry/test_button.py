"""Test the Teslemetry button platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import InsufficientCredits

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, METADATA

VIN = "LRW3F7EK4NC700000"

CREDITS_AVAILABLE_EVENT = {
    "credits": {
        "type": "command",
        "cost": 1,
        "name": "command",
        "quota": {
            "used": 5,
            "fraction": 0.5,
            "reset_at": "2026-07-10T00:00:00.000Z",
        },
        "balance": 0,
    },
    "createdAt": "2024-10-04T10:45:17.537Z",
}
CREDITS_INSUFFICIENT_EVENT = {
    "credits": {
        "type": "command",
        "cost": 1,
        "name": "command",
        "quota": {
            "used": 10,
            "fraction": 1.0,
            "reset_at": "2026-07-10T00:00:00.000Z",
        },
        "balance": 0,
    },
    "createdAt": "2024-10-04T10:45:18.537Z",
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the button entities are correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("name", "func", "args", "kwargs"),
    [
        ("wake", "wake_up", (), {}),
        ("flash_lights", "flash_lights", (), {}),
        ("honk_horn", "honk_horn", (), {}),
        ("keyless_driving", "remote_start_drive", (), {}),
        ("play_fart", "remote_boombox", (0,), {}),
        (
            "homelink",
            "trigger_homelink",
            (),
            {"lat": 32.87336, "lon": -117.22743},
        ),
        (
            "enable_keep_accessory_power",
            "set_keep_accessory_power_mode",
            (True,),
            {},
        ),
        (
            "disable_keep_accessory_power",
            "set_keep_accessory_power_mode",
            (False,),
            {},
        ),
    ],
)
async def test_press(
    hass: HomeAssistant,
    name: str,
    func: str,
    args: tuple[bool | int, ...],
    kwargs: dict[str, float],
) -> None:
    """Test pressing the API buttons."""
    await setup_platform(hass, [Platform.BUTTON])

    with patch(
        f"tesla_fleet_api.teslemetry.Vehicle.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [f"button.test_{name}"]},
            blocking=True,
        )
        command.assert_called_once_with(*args, **kwargs)


async def test_insufficient_credits(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is raised when the account is out of command credits."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.wake_up",
            side_effect=InsufficientCredits,
        ),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )

    # Assert the specific insufficient_credits error, not the generic
    # command_exception fallthrough, so the user-facing message cannot regress.
    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "insufficient_credits"

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue
    # Setup does not re-probe credits, so the repair must survive a restart.
    assert issue.is_persistent

    # A subsequent successful command does not clear the repair; only a credits
    # stream event does, since not every command consumes command credits.
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ["button.test_wake"]},
        blocking=True,
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_insufficient_credits_not_recreated_after_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a command that settles after its entry unloaded creates no repair."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    async def unload_then_fail() -> None:
        # The entry finishes unloading while this command is still in flight.
        assert await hass.config_entries.async_unload(entry.entry_id)
        raise InsufficientCredits

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.wake_up",
            side_effect=unload_then_fail,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_insufficient_credits_not_recreated_after_reload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_add_listener: AsyncMock,
) -> None:
    """Test a command that settles after its entry reloaded creates no repair."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    async def reload_then_fail() -> None:
        # The entry reloads and its new stream reports credits available, all
        # while this command is still in flight.
        await reload_platform(hass, entry, [Platform.BUTTON])
        mock_add_listener.send(CREDITS_AVAILABLE_EVENT)
        raise InsufficientCredits

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.wake_up",
            side_effect=reload_then_fail,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )

    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("events", "created"),
    [
        pytest.param([CREDITS_AVAILABLE_EVENT], False, id="available"),
        pytest.param(
            [CREDITS_AVAILABLE_EVENT, CREDITS_INSUFFICIENT_EVENT],
            True,
            id="available_then_insufficient",
        ),
    ],
)
async def test_insufficient_credits_events_while_in_flight(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_add_listener: AsyncMock,
    events: list[dict[str, object]],
    created: bool,
) -> None:
    """Test the newest credits event during a command decides on the repair."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    async def send_credits_then_fail() -> None:
        for event in events:
            mock_add_listener.send(event)
        raise InsufficientCredits

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.wake_up",
            side_effect=send_credits_then_fail,
        ),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )

    # The command fails for the caller either way.
    assert error.value.translation_key == "insufficient_credits"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert (issue is not None) is created


@pytest.mark.parametrize(
    ("firmware", "expected"),
    [
        pytest.param("2025.32", False, id="below_threshold"),
        pytest.param("2025.38", True, id="at_threshold"),
    ],
)
async def test_keep_accessory_power_firmware_gate(
    hass: HomeAssistant,
    mock_metadata: AsyncMock,
    firmware: str,
    expected: bool,
) -> None:
    """Tests that keep accessory power buttons require firmware >= 2025.38."""

    metadata = deepcopy(METADATA)
    metadata["vehicles"][VIN]["firmware"] = firmware
    mock_metadata.return_value = metadata

    await setup_platform(hass, [Platform.BUTTON])

    # An ungated button proves setup ran, so a missing gated button is the gate.
    assert hass.states.get("button.test_wake") is not None
    assert (
        hass.states.get("button.test_enable_keep_accessory_power") is not None
    ) == expected
    assert (
        hass.states.get("button.test_disable_keep_accessory_power") is not None
    ) == expected
