"""Tests for SLZB-Ultima remote entity."""

from unittest.mock import MagicMock, patch

from pysmlight import Info
from pysmlight.exceptions import SmlightError
from pysmlight.models import IRPayload
import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.REMOTE]


MOCK_ULTIMA = Info(
    MAC="AA:BB:CC:DD:EE:FF",
    model="SLZB-Ultima3",
)


async def test_remote_setup_ultima(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test remote entity is created for Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("remote.mock_title_ir_remote")
    assert state is not None


async def test_remote_not_created_non_ultima(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test remote entity is not created for non-Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR1",
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("remote.mock_title_ir_remote")
    assert state is None


async def test_remote_send_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test sending IR command."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.mock_title_ir_remote"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COMMAND: ["my_code", "another_code"],
            ATTR_DELAY_SECS: 0,
        },
        blocking=True,
    )

    assert mock_smlight_client.actions.send_ir_code.call_count == 2
    mock_smlight_client.actions.send_ir_code.assert_any_call(IRPayload(code="my_code"))
    mock_smlight_client.actions.send_ir_code.assert_any_call(
        IRPayload(code="another_code")
    )


async def test_remote_send_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test connection error handling."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.mock_title_ir_remote"
    state = hass.states.get(entity_id)
    assert state is not None

    mock_smlight_client.actions.send_ir_code.side_effect = SmlightError("Failed")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: ["my_code"]},
            blocking=True,
        )
    assert exc_info.value.translation_key == "send_ir_code_failed"


@patch("homeassistant.components.smlight.remote.asyncio.sleep")
async def test_remote_send_command_repeats(
    mock_sleep: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test sending IR command with repeats and delay."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "remote.mock_title_ir_remote"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COMMAND: ["my_code", "another_code"],
            ATTR_NUM_REPEATS: 2,
            ATTR_DELAY_SECS: 0.5,
        },
        blocking=True,
    )

    assert mock_smlight_client.actions.send_ir_code.call_count == 4
    assert mock_sleep.call_count == 5
    mock_sleep.assert_called_with(0.5)
