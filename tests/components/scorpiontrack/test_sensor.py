"""Test the ScorpionTrack sensor platform."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
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
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SPEED_ENTITY_ID = "sensor.ab12_cde_speed"
LAST_REPORTED_ENTITY_ID = "sensor.ab12_cde_last_reported"
HEADING_ENTITY_ID = "sensor.ab12_cde_heading"
SENSOR_ENTITY_IDS = (
    SPEED_ENTITY_ID,
    LAST_REPORTED_ENTITY_ID,
    HEADING_ENTITY_ID,
)


def test_sensor_platform_is_forwarded() -> None:
    """Test the config entry forwards the sensor platform."""
    assert Platform.SENSOR in PLATFORMS


def _get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return an entity state that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.fixture(autouse=True)
def sensor_platform_only() -> Iterator[None]:
    """Set up only the sensor platform."""
    with patch("homeassistant.components.scorpiontrack.PLATFORMS", (Platform.SENSOR,)):
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor state, metadata, identifiers, and device assignment."""
    position = replace(
        mock_share.vehicles[0].position,
        timestamp=datetime(2026, 7, 16, 12, tzinfo=UTC),
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(replace(mock_share.vehicles[0], position=position),)
    )
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_heading_is_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test heading is disabled by the integration by default."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(HEADING_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("distance_units", "expected_state", "expected_unit"),
    [
        pytest.param(
            "miles",
            "30.0122285850632",
            UnitOfSpeed.MILES_PER_HOUR,
            id="miles-display",
        ),
        pytest.param(
            "kilometers",
            "48.3",
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            id="metric-display",
        ),
    ],
)
async def test_speed_display_unit_uses_share_preference_with_kmh_native_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    distance_units: str,
    expected_state: str,
    expected_unit: UnitOfSpeed,
) -> None:
    """Test speed display units while API values remain native km/h."""
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, distance_units=distance_units
    )

    await setup_integration(hass, mock_config_entry)

    state = _get_state(hass, SPEED_ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == expected_unit
    assert mock_share.vehicles[0].position.speed_kmh == 48.3


async def test_speed_user_unit_override_survives_refresh_and_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a user speed-unit override remains owned by Home Assistant."""
    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity_options(
        SPEED_ENTITY_ID,
        Platform.SENSOR,
        {"unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR},
    )
    await hass.async_block_till_done()

    updated_position = replace(mock_share.vehicles[0].position, speed_kmh=64.4)
    metric_share = replace(
        mock_share,
        distance_units="kilometers",
        vehicles=(replace(mock_share.vehicles[0], position=updated_position),),
    )
    await _async_refresh(hass, freezer, mock_scorpiontrack_client, metric_share)

    state = _get_state(hass, SPEED_ENTITY_ID)
    assert state.state == "64.4"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.KILOMETERS_PER_HOUR

    reloaded_position = replace(updated_position, speed_kmh=80.5)
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        distance_units="miles",
        vehicles=(replace(mock_share.vehicles[0], position=reloaded_position),),
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = _get_state(hass, SPEED_ENTITY_ID)
    assert state.state == "80.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.KILOMETERS_PER_HOUR


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zero_sensor_values_are_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test zero speed and heading values remain available."""
    position = replace(mock_share.vehicles[0].position, speed_kmh=0, bearing=0)
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(replace(mock_share.vehicles[0], position=position),)
    )

    await setup_integration(hass, mock_config_entry)

    assert _get_state(hass, SPEED_ENTITY_ID).state == "0.0"
    assert _get_state(hass, HEADING_ENTITY_ID).state == "0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_none_sensor_values_are_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test absent sensor values are unavailable."""
    position = replace(
        mock_share.vehicles[0].position,
        speed_kmh=None,
        timestamp=None,
        bearing=None,
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(replace(mock_share.vehicles[0], position=position),)
    )

    await setup_integration(hass, mock_config_entry)

    assert {_get_state(hass, entity_id).state for entity_id in SENSOR_ENTITY_IDS} == {
        STATE_UNAVAILABLE
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_removed_vehicle_makes_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test existing sensors become unavailable when their vehicle disappears."""
    await setup_integration(hass, mock_config_entry)

    await _async_refresh(
        hass,
        freezer,
        mock_scorpiontrack_client,
        replace(mock_share, vehicles=()),
    )

    assert {_get_state(hass, entity_id).state for entity_id in SENSOR_ENTITY_IDS} == {
        STATE_UNAVAILABLE
    }


async def test_new_vehicles_after_setup_do_not_add_sensor_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test vehicles added after setup do not add sensor entities."""
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

    assert hass.states.get("sensor.ef34_abc_speed") is None
    assert hass.states.get("sensor.ef34_abc_last_reported") is None
    assert hass.states.get("sensor.ef34_abc_heading") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_properties_use_coordinator_snapshot_without_coordinates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test sensor properties perform no I/O and expose no coordinates."""
    await setup_integration(hass, mock_config_entry)

    for entity_id in SENSOR_ENTITY_IDS:
        state = _get_state(hass, entity_id)
        assert ATTR_LATITUDE not in state.attributes
        assert ATTR_LONGITUDE not in state.attributes

    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_sensor_entities_reuse_vehicle_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensors use the existing vehicle device identity."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "101_1")})
    assert device is not None
    for entity_id in (SPEED_ENTITY_ID, LAST_REPORTED_ENTITY_ID):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == device.id
