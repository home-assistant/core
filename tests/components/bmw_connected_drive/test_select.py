"""Test BMW selects."""

from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWAPIError, MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import check_remote_service_call, setup_mocked_integration


async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all select entities
    assert hass.states.async_all("select") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "new_value", "old_value", "remote_service"),
    [
        (
            "select.i3_rex_charging_mode",
            "IMMEDIATE_CHARGING",
            "DELAYED_CHARGING",
            "charging-profile",
        ),
        ("select.i4_edrive40_ac_charging_limit", "12", "16", "charging-settings"),
        (
            "select.i4_edrive40_charging_mode",
            "DELAYED_CHARGING",
            "IMMEDIATE_CHARGING",
            "charging-profile",
        ),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    new_value: str,
    old_value: str,
    remote_service: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful input change."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(entity_id, old_value)
    assert hass.states.get(entity_id).state == old_value

    # Test
    await hass.services.async_call(
        "select",
        "select_option",
        service_data={"option": new_value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture, remote_service)
    assert hass.states.get(entity_id).state == new_value


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.i4_edrive40_ac_charging_limit", "17"),
        ("select.i4_edrive40_charging_mode", "BONKERS_MODE"),
    ],
)
async def test_service_call_invalid_input(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test not allowed values for select inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)
    old_value = hass.states.get(entity_id).state

    # Test
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "select",
            "select_option",
            service_data={"option": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (MyBMWRemoteServiceError, HomeAssistantError),
        (MyBMWAPIError, HomeAssistantError),
        (ServiceValidationError, ServiceValidationError),
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
    entity_id = "select.i4_edrive40_ac_charging_limit"
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
            "select",
            "select_option",
            service_data={"option": "16"},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value
