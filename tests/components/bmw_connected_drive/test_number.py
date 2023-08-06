"""Test BMW numbers."""
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
    """Test number options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all number entities
    assert hass.states.async_all("number") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.i4_edrive40_target_soc", "80"),
    ],
)
async def test_update_triggers_success(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test allowed values for number inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Test
    await hass.services.async_call(
        "number",
        "set_value",
        service_data={"value": value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 1


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.i4_edrive40_target_soc", "81"),
    ],
)
async def test_update_triggers_fail(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test not allowed values for number inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    BMWDataUpdateCoordinator.async_update_listeners.reset_mock()

    # Test
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "number",
            "set_value",
            service_data={"value": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 0


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
    """Test not allowed values for number inputs."""

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
            "number",
            "set_value",
            service_data={"value": "80"},
            blocking=True,
            target={"entity_id": "number.i4_edrive40_target_soc"},
        )
    assert BMWDataUpdateCoordinator.async_update_listeners.call_count == 0
