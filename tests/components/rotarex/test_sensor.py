"""Test the Rotarex sensors."""

from unittest.mock import AsyncMock

from rotarex_dimes_srg_api import RotarexSyncData, RotarexTank
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rotarex.sensor import RotarexTankSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities match snapshots."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device info matches snapshot."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-device")


async def test_sensor_uses_latest_sync(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors report the most recent synchronization data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Tank 1 has two syncs: 2024-01-01 and 2024-01-02.
    # The level sensor must use the latest (2024-01-02) value.
    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state
    assert level_state.state == "70.0"  # from 2024-01-02, not 75.5 from 2024-01-01

    # The timestamp sensor must also reflect the latest sync.
    ts_state = hass.states.get("sensor.tank_1_timestamp")
    assert ts_state
    assert ts_state.state == "2024-01-02T20:00:00+00:00"


async def test_tank_without_name_uses_guid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test that a tank without a name falls back to 'Tank <guid>'."""
    mock_rotarex_api.fetch_tanks.return_value = [
        RotarexTank(
            guid="no-name-guid",
            name="",
            synch_datas=[
                RotarexSyncData(
                    synch_date="2024-03-01T08:00:00Z",
                    level=42.0,
                    battery=77.0,
                ),
            ],
        )
    ]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    level_state = hass.states.get("sensor.tank_no_name_guid_level")
    assert level_state is not None
    assert level_state.state == "42.0"


async def test_sensor_native_value_none_when_tank_disappears(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test native_value returns None when tank disappears from coordinator data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Grab the level sensor entity for tank1 directly
    coordinator = mock_config_entry.runtime_data
    tank1_sensor: RotarexTankSensor | None = None
    for entity in hass.data["entity_components"]["sensor"].entities:
        if (
            hasattr(entity, "_tank_id")
            and entity._tank_id == "tank1-guid"
            and entity.entity_description.key == "level"
        ):
            tank1_sensor = entity
            break
    assert tank1_sensor is not None

    # Remove tank1 from coordinator data to simulate disappearance
    coordinator.data.pop("tank1-guid", None)

    # native_value must return None when tank is absent
    assert tank1_sensor.native_value is None
