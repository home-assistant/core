"""Tests for the Palazzetti sensor platform."""

from unittest.mock import AsyncMock, patch

from pypalazzetti.exceptions import CommunicationError, ValidationError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "number.stove_combustion_power"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.palazzetti.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_async_set_data(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting number data via service call."""
    await setup_integration(hass, mock_config_entry)

    # Set value: Success
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, "value": 1},
        blocking=True,
    )
    mock_palazzetti_client.set_power_mode.assert_called_once_with(1)
    mock_palazzetti_client.set_on.reset_mock()

    # Set value: Error
    mock_palazzetti_client.set_power_mode.side_effect = CommunicationError()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, "value": 1},
            blocking=True,
        )
    mock_palazzetti_client.set_on.reset_mock()

    mock_palazzetti_client.set_power_mode.side_effect = ValidationError()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, "value": 1},
            blocking=True,
        )
