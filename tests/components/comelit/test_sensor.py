"""Tests for Comelit SimpleHome sensor platform."""

from unittest.mock import AsyncMock, patch

from aiocomelit.api import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import (
    ALARM_AREA,
    ALARM_ZONE,
    OTHER,
    WATT,
    AlarmAreaState,
    AlarmZoneState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comelit.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.zone0"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.VEDO_PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_vedo_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_vedo_config_entry.entry_id,
    )


async def test_sensor_state_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test VEDO sensor unknown state."""

    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmZoneState.REST.value

    vedo_query = {
        ALARM_AREA: {
            0: ComelitVedoAreaObject(
                index=0,
                name="Area0",
                p1=True,
                p2=True,
                ready=False,
                armed=True,
                alarm=False,
                alarm_memory=False,
                sabotage=False,
                anomaly=False,
                in_time=False,
                out_time=False,
                human_status=AlarmAreaState.UNKNOWN,
            )
        },
        ALARM_ZONE: {
            0: ComelitVedoZoneObject(
                index=0,
                name="Zone0",
                status_api="0x000",
                status=0,
                human_status=AlarmZoneState.UNKNOWN,
            )
        },
    }

    mock_vedo.get_all_areas_and_zones.return_value = vedo_query

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_serial_bridge_sensor_dynamic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test Serial Bridge sensor dynamically added."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    entity_id = "sensor.switch0"
    entity_id_2 = "sensor.switch1"
    assert hass.states.get(entity_id)

    mock_serial_bridge.get_all_devices.return_value[OTHER] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Switch0",
            status=0,
            human_status="off",
            type="other",
            val=0,
            protected=0,
            zone="Bathroom",
            power=0.0,
            power_unit=WATT,
        ),
        1: ComelitSerialBridgeObject(
            index=1,
            name="Switch1",
            status=0,
            human_status="off",
            type="other",
            val=0,
            protected=0,
            zone="Bathroom",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id)
    assert hass.states.get(entity_id_2)


async def test_vedo_sensor_dynamic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test VEDO sensor dynamically added."""

    mock_vedo.reset_mock()
    await setup_integration(hass, mock_vedo_config_entry)

    assert hass.states.get(ENTITY_ID)

    entity_id_2 = "sensor.zone1"

    mock_vedo.get_all_areas_and_zones.return_value[ALARM_ZONE] = {
        0: ComelitVedoZoneObject(
            index=0,
            name="Zone0",
            status_api="0x000",
            status=0,
            human_status=AlarmZoneState.REST,
        ),
        1: ComelitVedoZoneObject(
            index=1,
            name="Zone1",
            status_api="0x000",
            status=0,
            human_status=AlarmZoneState.REST,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(entity_id_2)


@pytest.mark.parametrize(
    (
        "mock_fixture",
        "config_entry_fixture",
        "device_type",
        "expected_unique_id_suffix",
        "old_unique_id_removed",
    ),
    [
        (
            "mock_vedo",
            "mock_vedo_config_entry",
            "zone",
            "human_status-0",
            True,
        ),
        (
            "mock_serial_bridge",
            "mock_serial_bridge_config_entry",
            "other",
            "0",
            False,
        ),
    ],
)
async def test_migrate_sensor_unique_id(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_fixture: str,
    config_entry_fixture: str,
    device_type: str,
    expected_unique_id_suffix: str,
    old_unique_id_removed: bool,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor unique ID migration."""
    request.getfixturevalue(mock_fixture)
    config_entry = request.getfixturevalue(config_entry_fixture)
    config_entry.add_to_hass(hass)

    old_unique_id = f"{config_entry.entry_id}-0"
    new_unique_id = f"{config_entry.entry_id}-{expected_unique_id_suffix}"

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{config_entry.entry_id}-{device_type}-0")},
    )

    entity_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        old_unique_id,
        config_entry=config_entry,
        device_id=device.id,
    )

    await setup_integration(hass, config_entry)

    migrated_entry = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entry
    assert migrated_entry.unique_id == new_unique_id
    old_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, old_unique_id
    )
    assert (old_entity_id is None) is old_unique_id_removed
    assert (old_entity_id == entity_entry.entity_id) is not old_unique_id_removed
