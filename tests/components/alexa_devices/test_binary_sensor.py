"""Tests for the Alexa Devices binary sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aioamazondevices.const.sensors import SENSOR_STATE_OFF
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from aioamazondevices.structures import AmazonDeviceSensor
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import assert_device_removed_and_readded, setup_integration
from .const import (
    TEST_DEVICE_1,
    TEST_DEVICE_1_SENSORS,
    TEST_DEVICE_1_SN,
    TEST_DEVICE_2,
    TEST_DEVICE_2_SN,
)

MOTION_ENTITY_ID = "binary_sensor.echo_test_motion"
DETECTION_STATE = TEST_DEVICE_1_SENSORS["detectionState"]


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.alexa_devices.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotRetrieveData,
        CannotAuthenticate,
    ],
)
async def test_coordinator_data_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test coordinator data update exceptions."""

    entity_id = "binary_sensor.echo_test_connectivity"

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    mock_amazon_devices_client.get_devices_data.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test offline device handling."""

    entity_id = "binary_sensor.echo_test_connectivity"

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE


async def test_dynamic_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device added dynamically."""

    entity_id_1 = "binary_sensor.echo_test_connectivity"
    entity_id_2 = "binary_sensor.echo_test_2_connectivity"

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: TEST_DEVICE_1,
    }

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id_1))
    assert state.state == STATE_ON

    assert not hass.states.get(entity_id_2)

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: TEST_DEVICE_1,
        TEST_DEVICE_2_SN: TEST_DEVICE_2,
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id_1))
    assert state.state == STATE_ON

    assert (state := hass.states.get(entity_id_2))
    assert state.state == STATE_ON


async def test_device_removed_and_readded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are recreated when a device is removed and re-added."""
    await assert_device_removed_and_readded(
        hass,
        freezer,
        mock_amazon_devices_client,
        mock_config_entry,
        entity_id="binary_sensor.echo_test_2_connectivity",
        devices_with={TEST_DEVICE_1_SN: TEST_DEVICE_1, TEST_DEVICE_2_SN: TEST_DEVICE_2},
        devices_without={TEST_DEVICE_1_SN: TEST_DEVICE_1},
    )


@pytest.mark.parametrize(
    "key",
    [
        "bluetooth",
        "babyCryDetectionState",
        "beepingApplianceDetectionState",
        "coughDetectionState",
        "dogBarkDetectionState",
        "waterSoundsDetectionState",
    ],
)
async def test_deprecated_sensor_removal(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    key: str,
) -> None:
    """Test deprecated sensors are removed."""

    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Amazon",
        model="Echo Dot",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        unique_id=f"{TEST_DEVICE_1_SN}-{key}",
        device_id=device.id,
        config_entry=mock_config_entry,
        has_entity_name=True,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity2 = entity_registry.async_get(entity.entity_id)
    assert entity2 is None


@pytest.mark.parametrize(
    ("sensors", "expected_state"),
    [
        pytest.param({"detectionState": DETECTION_STATE}, STATE_ON, id="detected"),
        pytest.param(
            {"detectionState": replace(DETECTION_STATE, value=SENSOR_STATE_OFF)},
            STATE_OFF,
            id="not_detected",
        ),
        pytest.param(
            {"detectionState": replace(DETECTION_STATE, error=True)},
            STATE_UNAVAILABLE,
            id="error",
        ),
        pytest.param({}, STATE_UNAVAILABLE, id="no_value_yet"),
    ],
)
async def test_detection_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sensors: dict[str, AmazonDeviceSensor],
    expected_state: str,
) -> None:
    """Test the motion binary sensor state from the sensor store."""
    mock_amazon_devices_client.sensors = {TEST_DEVICE_1_SN: sensors}

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(MOTION_ENTITY_ID))
    assert state.state == expected_state


async def test_detection_state_unsupported(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no motion binary sensor is created without the feature."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].features.pop("motionSensor")

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.get(MOTION_ENTITY_ID)


async def test_detection_state_pushed(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a pushed sensor event updates the motion binary sensor."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(MOTION_ENTITY_ID))
    assert state.state == STATE_ON

    # The library mutates its store in place before signalling
    mock_amazon_devices_client.sensors[TEST_DEVICE_1_SN]["detectionState"] = replace(
        DETECTION_STATE, value=SENSOR_STATE_OFF
    )
    on_sensor_event = mock_amazon_devices_client.on_sensor_event.append.call_args[0][0]
    await on_sensor_event()
    await hass.async_block_till_done()

    assert (state := hass.states.get(MOTION_ENTITY_ID))
    assert state.state == STATE_OFF
