"""Tests for Roborock vacuums."""

import copy
from typing import Any
from unittest.mock import patch

import pytest
from roborock import RoborockException
from roborock.roborock_typing import RoborockCommand
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.const import GET_MAPS_SERVICE_NAME
from homeassistant.components.vacuum import (
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.roborock.mock_data import PROP

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"


async def test_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
) -> None:
    """Tests devices are registered in the entity registry."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


@pytest.mark.parametrize(
    ("service", "command", "service_params", "called_params"),
    [
        (SERVICE_START, RoborockCommand.APP_START, None, None),
        (SERVICE_PAUSE, RoborockCommand.APP_PAUSE, None, None),
        (SERVICE_STOP, RoborockCommand.APP_STOP, None, None),
        (SERVICE_RETURN_TO_BASE, RoborockCommand.APP_CHARGE, None, None),
        (SERVICE_CLEAN_SPOT, RoborockCommand.APP_SPOT, None, None),
        (SERVICE_LOCATE, RoborockCommand.FIND_ME, None, None),
        (
            SERVICE_SET_FAN_SPEED,
            RoborockCommand.SET_CUSTOM_MODE,
            {"fan_speed": "quiet"},
            [101],
        ),
        (
            SERVICE_SEND_COMMAND,
            RoborockCommand.GET_LED_STATUS,
            {"command": "get_led_status"},
            None,
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    service: str,
    command: str,
    service_params: dict[str, Any],
    called_params: list | None,
) -> None:
    """Test sending commands to the vacuum."""

    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID, **(service_params or {})}
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_command"
    ) as mock_send_command:
        await hass.services.async_call(
            Platform.VACUUM,
            service,
            data,
            blocking=True,
        )
        assert mock_send_command.call_count == 1
        assert mock_send_command.call_args[0][0] == command
        assert mock_send_command.call_args[0][1] == called_params


@pytest.mark.parametrize(
    ("in_cleaning_int", "expected_command"),
    [
        (0, RoborockCommand.APP_START),
        (1, RoborockCommand.APP_START),
        (2, RoborockCommand.RESUME_ZONED_CLEAN),
        (3, RoborockCommand.RESUME_SEGMENT_CLEAN),
    ],
)
async def test_resume_cleaning(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    in_cleaning_int: int,
    expected_command: RoborockCommand,
) -> None:
    """Test resuming clean on start button when a clean is paused."""
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = in_cleaning_int
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
        return_value=prop,
    ):
        await async_setup_component(hass, DOMAIN, {})
    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_command"
    ) as mock_send_command:
        await hass.services.async_call(
            Platform.VACUUM,
            SERVICE_START,
            data,
            blocking=True,
        )
        assert mock_send_command.call_count == 1
        assert mock_send_command.call_args[0][0] == expected_command


async def test_failed_user_command(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
) -> None:
    """Test that when a user sends an invalid command, we raise HomeAssistantError."""
    data = {ATTR_ENTITY_ID: ENTITY_ID, "command": "fake_command"}
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_command",
            side_effect=RoborockException(),
        ),
        pytest.raises(HomeAssistantError, match="Error while calling fake_command"),
    ):
        await hass.services.async_call(
            Platform.VACUUM,
            SERVICE_SEND_COMMAND,
            data,
            blocking=True,
        )


async def test_get_maps(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the service for maps correctly outputs rooms with the right name."""
    response = await hass.services.async_call(
        DOMAIN,
        GET_MAPS_SERVICE_NAME,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
