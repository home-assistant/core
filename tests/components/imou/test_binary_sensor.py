"""Tests for Imou binary sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    PARAM_DOOR_CONTACT_STATUS,
    UNKNOWN_BINARY_SENSOR_KEY,
    binary_sensor_mock_devices,
    create_online_device,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices", [binary_sensor_mock_devices], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot binary sensor entities created from the mock device list."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                binary_sensors={
                    UNKNOWN_BINARY_SENSOR_KEY: {PARAM_STATE: False},
                    PARAM_DOOR_CONTACT_STATUS: {PARAM_STATE: True},
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_binary_sensor_types(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown binary sensor keys from the API are not turned into entities."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    binary_sensor_entries = [
        entry for entry in entries if entry.domain == BINARY_SENSOR_DOMAIN
    ]
    assert len(binary_sensor_entries) == 1
    assert binary_sensor_entries[0].translation_key is None
    assert hass.states.get("binary_sensor.device_1_door") is not None


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    ("imou_mock_devices", "expected_state"),
    [
        (
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    button_keys=(),
                    binary_sensors={PARAM_DOOR_CONTACT_STATUS: {PARAM_STATE: True}},
                )
            ],
            STATE_ON,
        ),
        (
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    button_keys=(),
                    binary_sensors={PARAM_DOOR_CONTACT_STATUS: {PARAM_STATE: False}},
                )
            ],
            STATE_OFF,
        ),
    ],
    indirect=["imou_mock_devices"],
)
@pytest.mark.usefixtures("init_integration")
async def test_door_contact_state(
    hass: HomeAssistant,
    expected_state: str,
) -> None:
    """Door contact reports on when open and off when closed."""
    state = hass.states.get("binary_sensor.device_1_door")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices", [binary_sensor_mock_devices], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_added_for_device_discovered_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """A device added to the account after setup gets its binary sensor entity."""
    assert hass.states.get("binary_sensor.device_2_door") is None

    mock_imou_ha_device_manager.async_get_devices.return_value = [
        *binary_sensor_mock_devices(),
        create_online_device(
            "d2",
            "Device 2",
            button_keys=(),
            binary_sensors={PARAM_DOOR_CONTACT_STATUS: {PARAM_STATE: False}},
        ),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.device_2_door")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices", [binary_sensor_mock_devices], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_unavailable_when_device_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Binary sensors become unavailable when the device is offline."""

    async def set_device_offline(device: ImouHaDevice) -> None:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.OFFLINE.value}

    mock_imou_ha_device_manager.async_update_device_status.side_effect = (
        set_device_offline
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.device_1_door")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices", [binary_sensor_mock_devices], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Binary sensor entities are removed when the device is no longer on the account."""
    assert hass.states.get("binary_sensor.device_1_door").state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get("binary_sensor.device_1_door") is None
