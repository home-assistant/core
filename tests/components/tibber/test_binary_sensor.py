"""Tests for the Tibber binary sensors."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .conftest import create_tibber_device

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensor_snapshot(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor entities against snapshot."""
    device = create_tibber_device(
        connector_status="connected",
        charging_status="charging",
        device_status="on",
        is_online="true",
    )
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_binary_sensors_with_empty_external_ids(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensors migrate empty external ID registry entries."""
    area = area_registry.async_get_or_create("Outside")
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "")},
        name="Charger left",
    )
    legacy_device = device_registry.async_update_device(
        legacy_device.id, area_id=area.id
    )
    assert legacy_device is not None

    right_legacy_entity = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "charger-right_connector.status",
        suggested_object_id="legacy_right_connector_status",
        config_entry=config_entry,
        device_id=legacy_device.id,
    )
    left_legacy_entity = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "charger-left_connector.status",
        suggested_object_id="legacy_connector_status",
        config_entry=config_entry,
        device_id=legacy_device.id,
    )
    devices = {
        device_id: create_tibber_device(
            device_id=device_id,
            external_id="",
            name=name,
            connector_status="connected",
        )
        for device_id, name in (
            ("charger-left", "Charger left"),
            ("charger-right", "Charger right"),
        )
    }
    data_api_client_mock.get_all_devices = AsyncMock(return_value=devices)
    data_api_client_mock.update_devices = AsyncMock(return_value=devices)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    left_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "charger-left_connector.status"
    )
    right_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "charger-right_connector.status"
    )
    assert left_entity_id is not None
    assert right_entity_id is not None
    assert left_entity_id == left_legacy_entity.entity_id
    assert right_entity_id == right_legacy_entity.entity_id

    left_entity = entity_registry.async_get(left_entity_id)
    right_entity = entity_registry.async_get(right_entity_id)
    assert left_entity is not None
    assert right_entity is not None
    assert left_entity.device_id != right_entity.device_id

    left_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "charger-left"), config_entry.entry_id
    )
    right_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "charger-right"), config_entry.entry_id
    )
    assert left_device is not None
    assert right_device is not None
    assert left_device.id == legacy_device.id
    assert left_device.area_id == area.id
    assert left_entity.device_id == left_device.id
    assert right_entity.device_id == right_device.id


@pytest.mark.parametrize(
    (
        "entity_suffix",
        "connector_status",
        "charging_status",
        "device_status",
        "is_online",
        "expected_state",
    ),
    [
        ("plug", "connected", None, None, None, STATE_ON),
        ("plug", "disconnected", None, None, None, STATE_OFF),
        ("charging", None, "charging", None, None, STATE_ON),
        ("charging", None, "idle", None, None, STATE_OFF),
        ("power", None, None, "on", None, STATE_ON),
        ("power", None, None, "off", None, STATE_OFF),
        ("connectivity", None, None, None, "true", STATE_ON),
        ("connectivity", None, None, None, "True", STATE_ON),
        ("connectivity", None, None, None, "false", STATE_OFF),
        ("connectivity", None, None, None, "False", STATE_OFF),
    ],
)
async def test_binary_sensor_states(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_suffix: str,
    connector_status: str | None,
    charging_status: str | None,
    device_status: str | None,
    is_online: str | None,
    expected_state: str,
) -> None:
    """Test binary sensor state values."""
    device = create_tibber_device(
        connector_status=connector_status,
        charging_status=charging_status,
        device_status=device_status,
        is_online=is_online,
    )
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.test_device_{entity_suffix}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
