"""Test BMW buttons."""
from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import check_remote_service_call, setup_mocked_integration


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
        ("button.i4_edrive40_find_vehicle"),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful button press."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)


async def test_service_call_fail(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed button press."""

    # Setup component
    assert await setup_mocked_integration(hass)
    entity_id = "switch.i4_edrive40_climate"
    old_value = hass.states.get(entity_id).state

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
            target={"entity_id": "button.i4_edrive40_activate_air_conditioning"},
        )
    assert hass.states.get(entity_id).state == old_value


@pytest.mark.parametrize(
    ("entity_id", "state_entity_id", "new_value", "old_value"),
    [
        (
            "button.i4_edrive40_activate_air_conditioning",
            "switch.i4_edrive40_climate",
            "on",
            "off",
        ),
        (
            "button.i4_edrive40_deactivate_air_conditioning",
            "switch.i4_edrive40_climate",
            "off",
            "on",
        ),
    ],
)
async def test_service_call_success_state_change(
    hass: HomeAssistant,
    entity_id: str,
    state_entity_id: str,
    new_value: str,
    old_value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful button press with state change."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(state_entity_id, old_value)
    assert hass.states.get(state_entity_id).state == old_value

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert hass.states.get(state_entity_id).state == new_value
