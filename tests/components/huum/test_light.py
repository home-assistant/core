"""Tests for the Huum light entity."""

from unittest.mock import AsyncMock, patch

from huum.exceptions import RequestError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN, LightService
from homeassistant.const import STATE_OFF, STATE_ON, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "light.huum_sauna_light"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


@pytest.mark.usefixtures("init_integration")
async def test_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_light_turn_off(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test turning off light."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_huum_client.toggle_light.assert_awaited_once()


async def test_light_turn_on(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on light."""
    mock_huum_client.status.return_value.light = 0

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.huum.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_huum_client.toggle_light.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_light_communication_error(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
) -> None:
    """Test that API errors when toggling the light are raised as HomeAssistantError."""
    mock_huum_client.toggle_light.side_effect = RequestError()

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the Huum sauna",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            LightService.TURN_OFF,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
