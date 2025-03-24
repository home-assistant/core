"""Test for Melissa climate component."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def test_setup_platform(
    hass: HomeAssistant, mock_melissa, snapshot: SnapshotAssertion
) -> None:
    """Test setup_platform."""
    await setup_integration(hass)

    assert hass.states.get("climate.melissa_12345678") == snapshot


async def test_actions(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_melissa: AsyncMock,
) -> None:
    """Test that the switch can be turned on and off."""
    await setup_integration(hass)

    entity_id = "climate.melissa_12345678"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(mock_melissa.return_value.async_send.mock_calls) == 2
