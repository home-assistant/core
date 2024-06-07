"""Test BMW locks."""

from unittest.mock import AsyncMock, patch

from bimmer_connected.models import MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
from freezegun import freeze_time
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import check_remote_service_call, setup_mocked_integration

from tests.common import snapshot_platform
from tests.components.recorder.common import async_wait_recording_done


@freeze_time("2023-06-22 10:30:00+00:00")
@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test lock states and attributes."""

    # Setup component
    with patch(
        "homeassistant.components.bmw_connected_drive.PLATFORMS", [Platform.LOCK]
    ):
        mock_config_entry = await setup_mocked_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("recorder_mock")
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
    """Test successful service call."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(entity_id, old_value)
    assert hass.states.get(entity_id).state == old_value

    now = dt_util.utcnow()

    # Test
    await hass.services.async_call(
        "lock",
        service,
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture, remote_service)
    assert hass.states.get(entity_id).state == new_value

    # wait for the recorder to really store the data
    await async_wait_recording_done(hass)
    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, [entity_id]
    )
    assert any(s for s in states[entity_id] if s.state == STATE_UNKNOWN) is False


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.usefixtures("recorder_mock")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed service call."""

    # Setup component
    assert await setup_mocked_integration(hass)
    old_value = hass.states.get(entity_id).state

    now = dt_util.utcnow()

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

    # wait for the recorder to really store the data
    await async_wait_recording_done(hass)
    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, [entity_id]
    )
    assert states[entity_id][-2].state == STATE_UNKNOWN
