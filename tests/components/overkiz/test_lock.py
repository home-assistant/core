"""Tests for the Overkiz lock platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

DOOR_LOCK = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/30",
    "lock.living_room_front_door",
)

SNAPSHOT_FIXTURES = [
    DOOR_LOCK,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to lock only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.LOCK]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_command"),
    [
        pytest.param(SERVICE_LOCK, "lock", id="lock"),
        pytest.param(SERVICE_UNLOCK, "unlock", id="unlock"),
    ],
)
async def test_lock_service_call(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    service: str,
    expected_command: str,
) -> None:
    """Test lock service calls send the correct commands."""
    await setup_overkiz_integration(fixture=DOOR_LOCK.fixture)

    await hass.services.async_call(
        LOCK_DOMAIN,
        service,
        {ATTR_ENTITY_ID: DOOR_LOCK.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DOOR_LOCK.device_url,
        command_name=expected_command,
    )


async def test_lock_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock reflects state changes from the device."""
    await setup_overkiz_integration(fixture=DOOR_LOCK.fixture)

    assert hass.states.get(DOOR_LOCK.entity_id).state == LockState.LOCKED

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=DOOR_LOCK.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_LOCKED_UNLOCKED.value,
                        "type": 3,
                        "value": "unlocked",
                    },
                ],
            )
        ],
    )

    assert hass.states.get(DOOR_LOCK.entity_id).state == LockState.UNLOCKED


async def test_lock_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=DOOR_LOCK.fixture)

    state = hass.states.get(DOOR_LOCK.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=DOOR_LOCK.device_url,
            )
        ],
    )

    assert hass.states.get(DOOR_LOCK.entity_id).state == STATE_UNAVAILABLE
