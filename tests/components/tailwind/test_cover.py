"""Tests for cover entities provided by the Tailwind integration."""
from unittest.mock import ANY, MagicMock

from gotailwind import (
    TailwindDoorDisabledError,
    TailwindDoorLockedOutError,
    TailwindDoorOperationCommand,
    TailwindError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.components.tailwind.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    "entity_id",
    [
        "cover.door_1",
        "cover.door_2",
    ],
)
async def test_cover_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test cover entities provided by the Tailwind integration."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_cover_operations(
    hass: HomeAssistant,
    mock_tailwind: MagicMock,
) -> None:
    """Test operating the doors."""
    assert len(mock_tailwind.operate.mock_calls) == 0
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: "cover.door_1",
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
            ATTR_ENTITY_ID: "cover.door_1",
        },
        blocking=True,
    )

    mock_tailwind.operate.assert_called_with(
        door=ANY, operation=TailwindDoorOperationCommand.CLOSE
    )

    # Test door disabled error handling
    mock_tailwind.operate.side_effect = TailwindDoorDisabledError("Door disabled")

    with pytest.raises(HomeAssistantError, match="Door disabled") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "door_disabled"

    with pytest.raises(HomeAssistantError, match="Door disabled") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "door_disabled"

    # Test door locked out error handling
    mock_tailwind.operate.side_effect = TailwindDoorLockedOutError("Door locked out")

    with pytest.raises(HomeAssistantError, match="Door locked out") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "door_locked_out"

    with pytest.raises(HomeAssistantError, match="Door locked out") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "door_locked_out"

    # Test door error handling
    mock_tailwind.operate.side_effect = TailwindError("Some error")

    with pytest.raises(HomeAssistantError, match="Some error") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "communication_error"

    with pytest.raises(HomeAssistantError, match="Some error") as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {
                ATTR_ENTITY_ID: "cover.door_1",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "communication_error"
