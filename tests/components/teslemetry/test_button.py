"""Test the Teslemetry button platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import InsufficientCredits

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import assert_entities, setup_platform
from .const import COMMAND_OK


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
    ("name", "func"),
    [
        ("wake", "wake_up"),
        ("flash_lights", "flash_lights"),
        ("honk_horn", "honk_horn"),
        ("keyless_driving", "remote_start_drive"),
        ("play_fart", "remote_boombox"),
        ("homelink", "trigger_homelink"),
    ],
)
async def test_press(hass: HomeAssistant, name: str, func: str) -> None:
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
        command.assert_called_once()


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

    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    # A subsequent successful command does not clear the repair; only a credits
    # stream event does, since not every command consumes command credits.
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ["button.test_wake"]},
        blocking=True,
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_insufficient_credits_stale_response_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_add_listener: AsyncMock,
) -> None:
    """Test a stale InsufficientCredits response does not recreate a cleared repair."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    async def send_credits_then_fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # A credits-availability event lands while this command is still in
        # flight, then the older response finally raises InsufficientCredits.
        mock_add_listener.send(
            {
                "credits": {
                    "type": "command",
                    "cost": 1,
                    "quota": {
                        "used": 5,
                        "fraction": 0.5,
                        "reset_at": "2026-07-10T00:00:00.000Z",
                    },
                    "balance": 0,
                },
                "createdAt": "2024-10-04T10:45:17.537Z",
            }
        )
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

    # The command still fails for the caller, but credits are already reported
    # available so the stale response must not recreate the repair.
    assert error.value.translation_key == "insufficient_credits"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_insufficient_credits_available_then_insufficient(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_add_listener: AsyncMock,
) -> None:
    """Test the repair is created when the newest mid-flight state is insufficient."""
    entry = await setup_platform(hass, [Platform.BUTTON])
    issue_id = f"insufficient_credits_{entry.entry_id}"

    async def send_credits_then_fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Credits are briefly reported available, then reported insufficient
        # again, all while this command is still in flight.
        mock_add_listener.send(
            {
                "credits": {
                    "type": "command",
                    "cost": 1,
                    "quota": {
                        "used": 5,
                        "fraction": 0.5,
                        "reset_at": "2026-07-10T00:00:00.000Z",
                    },
                    "balance": 0,
                },
                "createdAt": "2024-10-04T10:45:17.537Z",
            }
        )
        mock_add_listener.send(
            {
                "credits": {
                    "type": "command",
                    "cost": 1,
                    "quota": {
                        "used": 10,
                        "fraction": 1.0,
                        "reset_at": "2026-07-10T00:00:00.000Z",
                    },
                    "balance": 0,
                },
                "createdAt": "2024-10-04T10:45:18.537Z",
            }
        )
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

    # The newest credit state seen since the command started is insufficient, so
    # the account really is out of credits and the repair must be created.
    assert error.value.translation_key == "insufficient_credits"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
