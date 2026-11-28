"""Tests for the Palazzetti light platform."""

from unittest.mock import AsyncMock, patch

from pypalazzetti.exceptions import CommunicationError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN, LightService
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "light.stove_light"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.palazzetti.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_async_turn_on(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light via service call."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_palazzetti_client.set_light.assert_called_once_with(True)


async def test_async_turn_off(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off the light via service call."""
    mock_palazzetti_client.is_light_on = True
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_palazzetti_client.set_light.assert_called_once_with(False)


@pytest.mark.parametrize(
    ("service", "method_arg"),
    [
        pytest.param(LightService.TURN_ON, True, id="turn_on"),
        pytest.param(LightService.TURN_OFF, False, id="turn_off"),
    ],
)
async def test_async_turn_on_off_error(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: LightService,
    method_arg: bool,
) -> None:
    """Test error handling during turn on/off."""
    mock_palazzetti_client.set_light.side_effect = CommunicationError()
    await setup_integration(hass, mock_config_entry)

    error_message = "Could not connect to the device"
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_palazzetti_client.set_light.assert_called_once_with(method_arg)


@pytest.mark.parametrize(
    ("service", "method_arg"),
    [
        pytest.param(LightService.TURN_ON, True, id="turn_on"),
        pytest.param(LightService.TURN_OFF, False, id="turn_off"),
    ],
)
async def test_async_turn_on_off_rejected(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: LightService,
    method_arg: bool,
) -> None:
    """Test error handling when device rejects turn on/off."""
    mock_palazzetti_client.set_light.return_value = False
    await setup_integration(hass, mock_config_entry)

    error_message = "Could not connect to the device"
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_palazzetti_client.set_light.assert_called_once_with(method_arg)


async def test_no_light_control(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that light entity is not created when light control is unavailable."""
    mock_palazzetti_client.has_light_control = False
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None
