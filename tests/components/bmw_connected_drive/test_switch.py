"""Test BMW switches."""
from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWAPIError, MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bmw_connected_drive.coordinator import (
    BMWDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import check_remote_service_call, setup_mocked_integration


async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all switch entities
    assert hass.states.async_all("switch") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("switch.i4_edrive40_climate", "ON"),
        ("switch.i4_edrive40_climate", "OFF"),
        ("switch.iX_xdrive50_charging", "ON"),
        ("switch.iX_xdrive50_charging", "OFF"),
    ],
)
async def test_update_triggers_success(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test allowed values for switch inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Test
    await hass.services.async_call(
        "switch",
        f"turn_{value.lower()}",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 1


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (MyBMWRemoteServiceError, HomeAssistantError),
        (MyBMWAPIError, HomeAssistantError),
        (ValueError, ValueError),
    ],
)
async def test_update_triggers_exceptions(
    hass: HomeAssistant,
    raised: Exception,
    expected: Exception,
    bmw_fixture: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test not allowed values for switch inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Setup exception
    monkeypatch.setattr(
        RemoteServices,
        "trigger_remote_service",
        AsyncMock(side_effect=raised),
    )

    # Test
    with pytest.raises(expected):
        await hass.services.async_call(
            "switch",
            "turn_on",
            blocking=True,
            target={"entity_id": "switch.i4_edrive40_climate"},
        )
    with pytest.raises(expected):
        await hass.services.async_call(
            "switch",
            "turn_off",
            blocking=True,
            target={"entity_id": "switch.i4_edrive40_climate"},
        )
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 0
