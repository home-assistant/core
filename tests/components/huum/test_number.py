"""Tests for the Huum number entity."""

from unittest.mock import AsyncMock

from huum.const import SaunaStatus
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "number.huum_sauna_humidity"


async def test_number_entity(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_humidity(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the humidity."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    mock_huum.status = SaunaStatus.ONLINE_HEATING
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 5,
        },
        blocking=True,
    )

    mock_huum.turn_on.assert_called_once_with(temperature=80, humidity=5)


async def test_dont_set_humidity_when_sauna_not_heating(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the humidity."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    mock_huum.status = SaunaStatus.ONLINE_NOT_HEATING
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 5,
        },
        blocking=True,
    )

    mock_huum.turn_on.assert_not_called()
