"""Tests for the Watts Vision switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    with patch("homeassistant.components.watts.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_state(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.living_room_switch")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_state: bool,
) -> None:
    """Test turning switch on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.living_room_switch"},
        blocking=True,
    )

    mock_watts_client.set_switch_state.assert_called_once_with(
        "switch_789", expected_state
    )


async def test_fast_polling(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that turning on triggers fast polling and it stops after duration."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.living_room_switch"},
        blocking=True,
    )

    mock_watts_client.get_device.reset_mock()

    # Fast polling should be active
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called
    mock_watts_client.get_device.assert_called_with("switch_789", refresh=True)

    # Should still be in fast polling after 55s
    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=50))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called

    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Fast polling should be done now
    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_watts_client.get_device.called


@pytest.mark.parametrize(
    "service",
    [SERVICE_TURN_ON, SERVICE_TURN_OFF],
)
async def test_api_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test error handling when turning on/off fails."""
    await setup_integration(hass, mock_config_entry)

    mock_watts_client.set_switch_state.side_effect = RuntimeError("API Error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the switch state"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "switch.living_room_switch"},
            blocking=True,
        )
