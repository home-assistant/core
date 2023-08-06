"""Test BMW switches."""
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
    """Test switch options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all switch entities
    assert hass.states.async_all("switch") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "new_value", "old_value"),
    [
        ("switch.i4_edrive40_climate", "on", "off"),
        ("switch.i4_edrive40_climate", "off", "on"),
        ("switch.iX_xdrive50_charging", "on", "off"),
        ("switch.iX_xdrive50_charging", "off", "on"),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    new_value: str,
    old_value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful switch change."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(entity_id, old_value)
    assert hass.states.get(entity_id).state == old_value

    # Test
    await hass.services.async_call(
        "switch",
        f"turn_{new_value}",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert hass.states.get(entity_id).state == new_value


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
    entity_id = "switch.i4_edrive40_climate"
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
            "switch",
            "turn_off",
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value
