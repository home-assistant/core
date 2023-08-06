"""Test BMW numbers."""
from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWAPIError, MyBMWRemoteServiceError
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
    """Test number options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all number entities
    assert hass.states.async_all("number") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "new_value", "old_value"),
    [
        ("number.i4_edrive40_target_soc", "80", "100"),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    new_value: str,
    old_value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful number change."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(entity_id, old_value)
    assert hass.states.get(entity_id).state == old_value

    # Test
    await hass.services.async_call(
        "number",
        "set_value",
        service_data={"value": new_value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert hass.states.get(entity_id).state == new_value


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.i4_edrive40_target_soc", "81"),
    ],
)
async def test_service_call_invalid_input(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test not allowed values for number inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    old_value = hass.states.get(entity_id).state

    # Test
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "number",
            "set_value",
            service_data={"value": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (MyBMWRemoteServiceError, HomeAssistantError),
        (MyBMWAPIError, HomeAssistantError),
        (ValueError, ValueError),
    ],
)
async def test_service_call_fail(
    hass: HomeAssistant,
    raised: Exception,
    expected: Exception,
    bmw_fixture: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exception handling."""

    # Setup component
    assert await setup_mocked_integration(hass)
    entity_id = "number.i4_edrive40_target_soc"
    old_value = hass.states.get(entity_id).state

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
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value
