"""Tests for cover entities provided by the Tailwind integration."""
from unittest.mock import ANY, MagicMock

from gotailwind import TailwindDoorOperationCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_cover_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_tailwind: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover entities provided by the Tailwind integration."""
    for entity_id in (
        "cover.door_1",
        "cover.door_2",
    ):
        assert (state := hass.states.get(entity_id))
        assert state == snapshot(name=entity_id)

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert entity_entry == snapshot(name=entity_id)

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry == snapshot(name=entity_id)

    # Test operating the doors
    assert len(mock_tailwind.operate.mock_calls) == 0
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_tailwind.operate.assert_called_with(
        door=ANY, operation=TailwindDoorOperationCommand.OPEN
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_tailwind.operate.assert_called_with(
        door=ANY, operation=TailwindDoorOperationCommand.CLOSE
    )
