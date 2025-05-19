"""Tests for miele light module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = LIGHT_DOMAIN
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "light.hood_light"


async def test_light_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test light entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize(
    ("service", "light_state"),
    [
        (SERVICE_TURN_ON, 1),
        (SERVICE_TURN_OFF, 2),
    ],
)
async def test_light_toggle(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
    service: str,
    light_state: int,
) -> None:
    """Test the light can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_miele_client.send_action.assert_called_once_with(
        "DummyAppliance_18", {"light": light_state}
    )


@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
    service: str,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    mock_miele_client.send_action.assert_called_once()
