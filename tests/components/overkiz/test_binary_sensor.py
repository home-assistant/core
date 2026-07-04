"""Tests for the Overkiz binary sensor platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_state_changed_event,
    device_unavailable_event,
)

from tests.common import snapshot_platform

SMOKE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/8907539",
    "binary_sensor.maple_residence_living_room_smoke_detector_smoke",
)
HEATING_STATUS = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#1",
    "binary_sensor.my_home_patio_water_heating_heating_status",
)
CONTACT_SENSOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "rtds://1234-1234-6233/394781",
    "binary_sensor.family_wing_porte_contact",
)

SNAPSHOT_FIXTURES = [
    SMOKE_SENSOR,
    HEATING_STATUS,
    CONTACT_SENSOR,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to binary_sensor only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_binary_sensor_smoke_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a smoke sensor (notDetected → detected)."""
    await setup_overkiz_integration(fixture=SMOKE_SENSOR.fixture)

    state = hass.states.get(SMOKE_SENSOR.entity_id)
    assert state
    assert state.state == STATE_OFF

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                SMOKE_SENSOR.device_url,
                [
                    {
                        "name": OverkizState.CORE_SMOKE.value,
                        "type": 3,
                        "value": "detected",
                    },
                ],
            )
        ],
    )

    state = hass.states.get(SMOKE_SENSOR.entity_id)
    assert state
    assert state.state == STATE_ON


async def test_binary_sensor_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=SMOKE_SENSOR.fixture)

    state = hass.states.get(SMOKE_SENSOR.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [device_unavailable_event(SMOKE_SENSOR.device_url)],
    )

    state = hass.states.get(SMOKE_SENSOR.entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE
