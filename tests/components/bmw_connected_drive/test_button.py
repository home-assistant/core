"""Test BMW buttons."""
from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bmw_connected_drive.coordinator import (
    BMWDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_mocked_integration


async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button options and values."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all button entities
    assert hass.states.async_all("button") == snapshot


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.i4_edrive40_flash_lights"),
        ("button.i4_edrive40_sound_horn"),
        ("button.i4_edrive40_activate_air_conditioning"),
        ("button.i4_edrive40_deactivate_air_conditioning"),
        ("button.i4_edrive40_find_vehicle"),
    ],
)
async def test_update_triggers_success(
    hass: HomeAssistant,
    entity_id: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test button press."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert RemoteServices.trigger_remote_service.call_count == 1
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 1


async def test_update_failed(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test button press."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Setup exception
    monkeypatch.setattr(
        RemoteServices,
        "trigger_remote_service",
        AsyncMock(side_effect=MyBMWRemoteServiceError),
    )

    # Test
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            blocking=True,
            target={"entity_id": "button.i4_edrive40_flash_lights"},
        )
    assert RemoteServices.trigger_remote_service.call_count == 1
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 0
