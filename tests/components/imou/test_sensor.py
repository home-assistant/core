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
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    DEFAULT_SENSORS,
    UNKNOWN_SENSOR_KEY,
    create_online_device,
    sensor_mock_devices,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
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
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown sensor keys from the API are not turned into entities."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entries = [entry for entry in entries if entry.domain == SENSOR_DOMAIN]
    assert len(sensor_entries) == 2
    assert hass.states.get("sensor.device_1_battery") is not None


@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        pytest.param("sensor.device_1_status", "offline", id="status_reports_offline"),
        pytest.param(
            "sensor.device_1_battery", STATE_UNAVAILABLE, id="battery_unavailable"
        ),
    ],
)
@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_availability_when_device_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
    entity_id: str,
    expected_state: str,
) -> None:
    """Status stays available offline; other sensors become unavailable."""

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

    state = hass.states.get(entity_id)
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
    assert hass.states.get("sensor.device_1_battery").state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get("sensor.device_1_battery") is None


@pytest.mark.parametrize("imou_mock_devices", [sensor_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_storage_used_numeric_has_percentage_unit(hass: HomeAssistant) -> None:
    """Numeric storage used sensors expose a percentage unit."""
    state = hass.states.get("sensor.device_1_storage_used")
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
async def test_storage_used_error_codes_are_unknown(hass: HomeAssistant) -> None:
    """Storage error codes do not mix into the numeric storage_used state."""
    state = hass.states.get("sensor.device_1_storage_used")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("state_class") == "measurement"
