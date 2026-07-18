"""Test the ScorpionTrack binary sensor platform."""

from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackShare
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scorpiontrack.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

IGNITION_ENTITY_ID = "binary_sensor.ab12_cde_ignition"


def test_binary_sensor_platform_is_forwarded() -> None:
    """Test the config entry forwards the binary sensor platform."""
    assert Platform.BINARY_SENSOR in PLATFORMS


def _get_state(hass: HomeAssistant) -> State:
    """Return the ignition state that must exist."""
    state = hass.states.get(IGNITION_ENTITY_ID)
    assert state is not None
    return state


@pytest.fixture(autouse=True)
def binary_sensor_platform_only() -> Iterator[None]:
    """Set up only the binary sensor platform."""
    with patch(
        "homeassistant.components.scorpiontrack.PLATFORMS", (Platform.BINARY_SENSOR,)
    ):
        yield


async def _async_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_scorpiontrack_client: AsyncMock,
    share: ScorpionTrackShare,
) -> None:
    """Refresh the coordinator with the supplied share."""
    mock_scorpiontrack_client.async_get_share.return_value = share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_binary_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor state, metadata, identifiers, and device assignment."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("ignition", "expected_state"),
    [
        pytest.param(True, STATE_ON, id="on"),
        pytest.param(False, STATE_OFF, id="off"),
        pytest.param(None, STATE_UNAVAILABLE, id="unavailable"),
    ],
)
async def test_ignition_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    ignition: bool | None,
    expected_state: str,
) -> None:
    """Test true, false, and absent ignition values."""
    position = replace(mock_share.vehicles[0].position, ignition=ignition)
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(replace(mock_share.vehicles[0], position=position),)
    )

    await setup_integration(hass, mock_config_entry)

    assert _get_state(hass).state == expected_state


async def test_removed_vehicle_makes_ignition_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test ignition becomes unavailable when its vehicle disappears."""
    await setup_integration(hass, mock_config_entry)

    await _async_refresh(
        hass,
        freezer,
        mock_scorpiontrack_client,
        replace(mock_share, vehicles=()),
    )

    assert _get_state(hass).state == STATE_UNAVAILABLE


async def test_new_vehicles_after_setup_do_not_add_ignition_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test vehicles added after setup do not add ignition entities."""
    await setup_integration(hass, mock_config_entry)

    new_vehicle = replace(
        mock_share.vehicles[0],
        id=2,
        name="Tiguan",
        registration="EF34 ABC",
        model="Tiguan",
    )
    await _async_refresh(
        hass,
        freezer,
        mock_scorpiontrack_client,
        replace(mock_share, vehicles=(*mock_share.vehicles, new_vehicle)),
    )

    assert hass.states.get("binary_sensor.ef34_abc_ignition") is None


async def test_ignition_properties_use_coordinator_snapshot_without_coordinates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test ignition properties perform no I/O and expose no coordinates."""
    await setup_integration(hass, mock_config_entry)

    state = _get_state(hass)
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_ignition_reuses_vehicle_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ignition uses the existing vehicle device identity."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "101_1")})
    assert device is not None
    entry = entity_registry.async_get(IGNITION_ENTITY_ID)
    assert entry is not None
    assert entry.device_id == device.id
