"""Test BMW locks."""

from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
from freezegun import freeze_time
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import check_remote_service_call, setup_mocked_integration


@freeze_time("2023-06-22 10:30:00+00:00")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test lock states and attributes."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all select entities
    assert hass.states.async_all("lock") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "new_value", "old_value", "service", "remote_service"),
    [
        (
            "lock.m340i_xdrive_lock",
            "locked",
            "unlocked",
            "lock",
            "door-lock",
        ),
        ("lock.m340i_xdrive_lock", "unlocked", "locked", "unlock", "door-unlock"),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    new_value: str,
    old_value: str,
    service: str,
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
        "lock",
        service,
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture, remote_service)
    assert hass.states.get(entity_id).state == new_value


@pytest.mark.parametrize(
    ("entity_id", "service"),
    [
        ("lock.m340i_xdrive_lock", "lock"),
        ("lock.m340i_xdrive_lock", "unlock"),
    ],
)
async def test_service_call_fail(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    bmw_fixture: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed button press."""

    # Setup component
    assert await setup_mocked_integration(hass)
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
            "lock",
            service,
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert hass.states.get(entity_id).state == old_value
