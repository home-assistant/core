"""Tests for the Overkiz siren platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import ATTR_DURATION, DOMAIN as SIREN_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

SIREN = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "io://1234-5678-3293/2733989",
    "siren.siren",
)

SNAPSHOT_FIXTURES = [
    SIREN,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to siren only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SIREN]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_siren_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_siren_turn_on_default_duration(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on the siren with default duration (2 minutes)."""
    await setup_overkiz_integration(fixture=SIREN.fixture)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=SIREN.device_url,
        command_name="ringWithSingleSimpleSequence",
        parameters=[120000, 75, 2, "memorizedVolume"],
    )


async def test_siren_turn_on_custom_duration(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on the siren with a custom duration."""
    await setup_overkiz_integration(fixture=SIREN.fixture)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN.entity_id, ATTR_DURATION: 30},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=SIREN.device_url,
        command_name="ringWithSingleSimpleSequence",
        parameters=[30000, 75, 2, "memorizedVolume"],
    )


async def test_siren_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off the siren."""
    await setup_overkiz_integration(fixture=SIREN.fixture)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SIREN.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=SIREN.device_url,
        command_name="off",
    )


async def test_siren_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test siren becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=SIREN.fixture)

    state = hass.states.get(SIREN.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=SIREN.device_url,
            )
        ],
    )

    assert hass.states.get(SIREN.entity_id).state == STATE_UNAVAILABLE
