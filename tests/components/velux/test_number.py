"""Test Velux number entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pyvlx import Intensity

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.velux.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import update_callback_entity

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.NUMBER


def get_number_entity_id(mock: AsyncMock) -> str:
    """Helper to get the entity ID for a given mock node."""
    return f"number.{mock.name.lower().replace(' ', '_')}"


async def test_number_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate registry metadata."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_number_device_association(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure exterior heating number entity is associated with a device."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, mock_exterior_heating.serial_number) in device_entry.identifiers


async def test_get_intensity(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Entity state follows intensity value and becomes unknown when not known."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    # Set initial intensity values
    mock_exterior_heating.intensity.intensity_percent = 20
    await update_callback_entity(hass, mock_exterior_heating)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "20"

    mock_exterior_heating.intensity.known = False
    await update_callback_entity(hass, mock_exterior_heating)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_set_value_sets_intensity(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Calling set_value forwards to set_intensity."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 30, "entity_id": entity_id},
        blocking=True,
    )

    mock_exterior_heating.set_intensity.assert_awaited_once()
    args, kwargs = mock_exterior_heating.set_intensity.await_args
    intensity = args[0]
    assert isinstance(intensity, Intensity)
    assert intensity.intensity_percent == 30
    assert kwargs.get("wait_for_completion") is True


async def test_set_invalid_value_fails(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Values outside the valid range raise ServiceValidationError and do not call set_intensity."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 101, "entity_id": entity_id},
            blocking=True,
        )

    mock_exterior_heating.set_intensity.assert_not_awaited()
