"""Tests for the Palazzetti cover platform."""

from unittest.mock import AsyncMock, patch

from pypalazzetti.exceptions import CommunicationError, ValidationError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverService
from homeassistant.const import STATE_OPEN, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "cover.stove_door"


@pytest.mark.usefixtures("mock_palazzetti_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.palazzetti.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "open_state", "expected_call"),
    [
        pytest.param(CoverService.OPEN, False, True, id="open"),
        pytest.param(CoverService.CLOSE, True, False, id="close"),
    ],
)
async def test_async_open_close(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: CoverService,
    open_state: bool,
    expected_call: bool,
) -> None:
    """Test opening and closing the cover via service call."""
    mock_palazzetti_client.is_door_open = open_state
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_palazzetti_client.set_door.assert_called_once_with(expected_call)


@pytest.mark.parametrize(
    ("service", "method_arg"),
    [
        pytest.param(CoverService.OPEN, True, id="open"),
        pytest.param(CoverService.CLOSE, False, id="close"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        CommunicationError(),
        ValidationError("Door control is not available on this device"),
    ],
    ids=["communication_error", "validation_error"],
)
async def test_async_open_close_error(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: CoverService,
    method_arg: bool,
    exception: Exception,
) -> None:
    """Test error handling during open/close."""
    mock_palazzetti_client.set_door.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    error_message = "Could not connect to the device"
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_palazzetti_client.set_door.assert_called_once_with(method_arg)


@pytest.mark.parametrize(
    ("service", "method_arg"),
    [
        pytest.param(CoverService.OPEN, True, id="open"),
        pytest.param(CoverService.CLOSE, False, id="close"),
    ],
)
async def test_async_open_close_rejected(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: CoverService,
    method_arg: bool,
) -> None:
    """Test error handling when device rejects open/close."""
    mock_palazzetti_client.set_door.return_value = False
    await setup_integration(hass, mock_config_entry)

    error_message = "Could not connect to the device"
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_palazzetti_client.set_door.assert_called_once_with(method_arg)


async def test_no_door_control(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that cover entity is not created when door control is unavailable."""
    mock_palazzetti_client.has_door_control = False
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_door_state_open(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that door state is open when is_door_open is True."""
    mock_palazzetti_client.is_door_open = True
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OPEN
