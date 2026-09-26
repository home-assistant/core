"""Tests for the Beatbot sensor platform."""

from unittest.mock import MagicMock

from beatbot_cloud import BeatbotDeviceData
import pytest

from homeassistant.components.beatbot.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    BATTERY_ENTITY_ID,
    DEVICE_ID,
    ERROR_ENTITY_ID,
    INTERFACE_STATE,
    STATUS_ENTITY_ID,
    batch_state,
    create_device,
    setup_integration,
)

from tests.common import MockConfigEntry

ERROR_BITS = (1 << 2) | (1 << 6)
UNDECODABLE_ERROR_BITS = 1 << 23


@pytest.mark.parametrize(
    ("device", "states", "expected"),
    [
        pytest.param(create_device(), None, "cleaning", id="discovery"),
        pytest.param(
            create_device(),
            batch_state(states={INTERFACE_STATE: 2}),
            "charging",
            id="batch-state",
        ),
        pytest.param(
            create_device(work_status=999), None, STATE_UNKNOWN, id="unknown-status"
        ),
    ],
)
async def test_status_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    device: BeatbotDeviceData,
    states: dict | None,
    expected: str,
) -> None:
    """Expose the library-decoded work status."""
    mock_client.get_devices.return_value = [device]
    if states is not None:
        mock_client.get_device_states.return_value = states

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(STATUS_ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert "standby" in state.attributes["options"]


@pytest.mark.parametrize(
    ("error_code", "expected"),
    [
        pytest.param(0, "none", id="no-error"),
        pytest.param(ERROR_BITS, "power_low", id="decoded"),
        pytest.param(UNDECODABLE_ERROR_BITS, STATE_UNKNOWN, id="undecodable"),
    ],
)
async def test_error_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    error_code: int,
    expected: str,
) -> None:
    """Report a fault the library cannot decode as unknown, not as healthy."""
    mock_client.get_devices.return_value = [create_device(error_code=error_code)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ERROR_ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert "motor_error" in state.attributes["options"]


async def test_battery_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Expose battery percentage with measurement metadata."""
    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "80"
    assert state.attributes["device_class"] == SensorDeviceClass.BATTERY
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize(
    ("devices", "states"),
    [
        pytest.param([create_device()], batch_state(is_online=False), id="offline"),
        pytest.param([create_device()], {}, id="missing-batch-state"),
        pytest.param(
            [create_device(is_online=False)],
            batch_state(is_online=None),
            id="reported-offline",
        ),
    ],
)
async def test_sensors_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    devices: list[BeatbotDeviceData],
    states: dict,
) -> None:
    """Make sensors unavailable without a confirmed online state."""
    mock_client.get_devices.return_value = devices
    mock_client.get_device_states.return_value = states

    await setup_integration(hass, mock_config_entry)

    for entity_id in (STATUS_ENTITY_ID, BATTERY_ENTITY_ID, ERROR_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_unsupported_product_category_is_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose pool cleaners only; other product categories are skipped."""
    mock_client.get_devices.return_value = [
        create_device(),
        create_device("mower-1", name="Mower", product_category="lawn_mower"),
    ]

    await setup_integration(hass, mock_config_entry)

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{DEVICE_ID}_status"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, "mower-1_status")
        is None
    )


async def test_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose the Beatbot device metadata through the sensor entities."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{DEVICE_ID}_status"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    device = device_registry.async_get(entry.device_id)

    assert device is not None
    assert device.identifiers == {(DOMAIN, DEVICE_ID)}
    assert device.name == "AquaSense"
    assert device.manufacturer == "Beatbot"
    assert device.model == "AquaSense 2"
    assert device.model_id == "product-1"
    assert device.sw_version == "1.2.3"
