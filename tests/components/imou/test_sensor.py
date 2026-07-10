"""Tests for Imou sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_STATE_VARIANT,
    PARAM_STORAGE_USED,
    STATE_VARIANT_ENUM,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.const import PARAM_STATE, PARAM_STATUS
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    DEFAULT_SENSORS,
    UNKNOWN_SENSOR_KEY,
    create_online_device,
    sensor_mock_devices,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_sensor_platform_integration")
async def test_sensor_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot sensor entities created from the mock device list."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                sensors={
                    UNKNOWN_SENSOR_KEY: {PARAM_STATE: "1"},
                    PARAM_BATTERY: DEFAULT_SENSORS[PARAM_BATTERY],
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_sensor_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown sensor keys from the API are not turned into entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    sensor_entries = [entry for entry in entries if entry.domain == SENSOR_DOMAIN]
    assert len(sensor_entries) == 2
    battery_entries = [
        entry for entry in sensor_entries if entry.translation_key == PARAM_BATTERY
    ]
    assert len(battery_entries) == 1


@pytest.mark.parametrize(
    ("unique_id", "expected_state"),
    [
        pytest.param("d1$status", "offline", id="status_reports_offline"),
        pytest.param("d1$battery", STATE_UNAVAILABLE, id="battery_unavailable"),
    ],
)
@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_availability_when_device_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    unique_id: str,
    expected_state: str,
) -> None:
    """Status stays available offline; other sensors become unavailable."""
    entry = next(
        item
        for item in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if item.unique_id == unique_id
    )

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {
            PARAM_STATE: DeviceStatus.OFFLINE.value,
            PARAM_STATE_VARIANT: STATE_VARIANT_ENUM,
        }

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Sensor entities are removed when the device is no longer on the account."""
    battery_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$battery"
    )
    assert hass.states.get(battery_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get(battery_entry.entity_id) is None


@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_storage_used_numeric_has_percentage_unit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Numeric storage used sensors expose a percentage unit."""
    storage_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$storage_used"
    )
    state = hass.states.get(storage_entry.entity_id)
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == "%"


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                sensors={
                    PARAM_STATUS: DEFAULT_SENSORS[PARAM_STATUS],
                    PARAM_STORAGE_USED: {
                        PARAM_STATE: "e1",
                        PARAM_STATE_VARIANT: STATE_VARIANT_ENUM,
                    },
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_storage_used_enum_suppresses_numeric_metadata(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Enum storage_used values suppress unit, state class, and precision."""
    storage_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1$storage_used"
    )
    state = hass.states.get(storage_entry.entity_id)
    assert state is not None
    assert state.state == "e1"
    assert "unit_of_measurement" not in state.attributes
    assert "state_class" not in state.attributes
    assert (
        storage_entry.options.get("sensor", {}).get("suggested_display_precision")
        is None
    )
