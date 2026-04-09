"""Tests for SLZB-Ultima infrared entity."""

from unittest.mock import MagicMock

from infrared_protocols import Command, Timing
from pysmlight import Info
from pysmlight.exceptions import SmlightError
from pysmlight.models import IRPayload
import pytest

from homeassistant.components.infrared import async_send_command
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration

from tests.common import MockConfigEntry


class MockCommand(Command):
    """Mock InfraredCommand."""

    def __init__(self) -> None:
        """Initialize with fixed 38kHz modulation."""
        super().__init__(modulation=38000)

    def get_raw_timings(self) -> list[Timing]:
        """Return some fake timings."""
        return [Timing(high_us=9000, low_us=4500), Timing(high_us=560, low_us=1690)]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.INFRARED]


MOCK_ULTIMA = Info(
    MAC="AA:BB:CC:DD:EE:FF",
    model="SLZB-Ultima3",
)


async def test_infrared_setup_ultima(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test infrared entity is created for Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("infrared.mock_title_ir_emitter")
    assert state is not None


async def test_infrared_not_created_non_ultima(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test infrared entity is not created for non-Ultima devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR1",
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("infrared.mock_title_ir_emitter")
    assert state is None


async def test_infrared_send_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test sending IR command."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "infrared.mock_title_ir_emitter"
    state = hass.states.get(entity_id)
    assert state is not None

    await async_send_command(
        hass,
        entity_id,
        MockCommand(),
    )

    mock_smlight_client.actions.send_ir_code.assert_called_once_with(
        IRPayload.from_raw_timings([9000, 4500, 560, 1690], freq=38000)
    )


async def test_infrared_send_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test connection error handling."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "infrared.mock_title_ir_emitter"
    state = hass.states.get(entity_id)
    assert state is not None

    mock_smlight_client.actions.send_ir_code.side_effect = SmlightError("Failed")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_send_command(
            hass,
            entity_id,
            MockCommand(),
        )
    assert exc_info.value.translation_key == "send_ir_code_failed"


async def test_infrared_send_empty_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test ValueError from pysmlight is surfaced as HomeAssistantError."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "infrared.mock_title_ir_emitter"
    state = hass.states.get(entity_id)
    assert state is not None

    mock_smlight_client.actions.send_ir_code.side_effect = ValueError("empty payload")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_send_command(
            hass,
            entity_id,
            MockCommand(),
        )
    assert exc_info.value.translation_key == "send_ir_code_failed"


@pytest.mark.freeze_time("2025-09-03T22:00:00+00:00")
async def test_infrared_state_updated_after_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test that entity state is updated with a timestamp after a successful send."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ULTIMA
    await setup_integration(hass, mock_config_entry)

    entity_id = "infrared.mock_title_ir_emitter"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await async_send_command(hass, entity_id, MockCommand())

    state = hass.states.get(entity_id)
    assert state.state == "2025-09-03T22:00:00.000+00:00"
