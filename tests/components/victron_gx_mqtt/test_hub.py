"""Test the Victron GX MQTT Hub class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from victron_mqtt import (
    CannotConnectError,
    Device as VictronVenusDevice,
    Hub as VictronVenusHub,
    Metric as VictronVenusMetric,
    MetricKind,
)
from victron_mqtt.testing import create_mocked_hub, finalize_injection, inject_message

from homeassistant.components.victron_gx_mqtt.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)
from homeassistant.components.victron_gx_mqtt.hub import Hub
from homeassistant.components.victron_gx_mqtt.sensor import (
    VictronSensor,
    async_setup_entry as sensor_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MagicMock(spec=ConfigEntry)


@pytest.fixture
def basic_config():
    """Provide basic configuration."""
    return {
        CONF_HOST: "venus.local",
        CONF_PORT: 1883,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_SSL: False,
        CONF_INSTALLATION_ID: "12345",
        CONF_MODEL: "Venus GX",
        CONF_SERIAL: "HQ12345678",
        CONF_ROOT_TOPIC_PREFIX: "N/",
        CONF_UPDATE_FREQUENCY_SECONDS: 30,
    }


@pytest.fixture
def mock_victron_hub():
    """Create a mock VictronVenusHub."""
    with patch(
        "homeassistant.components.victron_gx_mqtt.hub.VictronVenusHub"
    ) as mock_hub_class:
        mock_hub = MagicMock(spec=VictronVenusHub)
        mock_hub.connect = AsyncMock()
        mock_hub.disconnect = AsyncMock()
        mock_hub.publish = MagicMock()
        mock_hub.installation_id = "12345"
        mock_hub_class.return_value = mock_hub
        yield mock_hub


@pytest.fixture
async def mqtt_test_setup(hass: HomeAssistant):
    """Set up MQTT testing with ALL platform callbacks."""
    victron_hub = await create_mocked_hub()
    mock_async_add_entities = MagicMock()

    # Create a real Hub and config entry
    mock_config_entry = MagicMock(spec=ConfigEntry)
    mock_config_entry.data = {
        CONF_HOST: "localhost",
        CONF_SERIAL: "test_serial",
    }
    mock_config_entry.unique_id = "test_unique_id"

    # Create the real Hub
    hub = Hub(hass, mock_config_entry)
    victron_hub.on_new_metric = hub._on_new_metric
    mock_config_entry.runtime_data = hub

    # Register all platform callbacks
    await sensor_setup_entry(hass, mock_config_entry, mock_async_add_entities)
    return victron_hub, mock_async_add_entities


async def test_hub_start_success(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test successful hub start."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)
    await hub.start()

    mock_victron_hub.connect.assert_called_once()


async def test_hub_start_connection_error(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test hub start with connection error."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"
    mock_victron_hub.connect.side_effect = CannotConnectError("Connection failed")

    hub = Hub(hass, mock_config_entry)

    with pytest.raises(ConfigEntryNotReady, match="Cannot connect to the hub"):
        await hub.start()


async def test_hub_stop(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test hub stop."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)
    await hub.stop()

    mock_victron_hub.disconnect.assert_called_once()


async def test_hub_stop_with_event(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test hub stop with event."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)
    mock_event = MagicMock()
    await hub.stop(mock_event)

    mock_victron_hub.disconnect.assert_called_once()


async def test_map_device_info() -> None:
    """Test _map_device_info static method."""
    mock_device = MagicMock(spec=VictronVenusDevice)
    mock_device.unique_id = "device_123"
    mock_device.manufacturer = "Victron Energy"
    mock_device.name = "Battery Monitor"
    mock_device.device_id = "288"
    mock_device.model = "BMV-712"
    mock_device.serial_number = "HQ12345678"

    installation_id = "12345"

    device_info = Hub._map_device_info(mock_device, installation_id)

    assert device_info.get("identifiers") == {(DOMAIN, "12345_device_123")}
    assert device_info.get("manufacturer") == "Victron Energy"
    assert device_info.get("name") == "Battery Monitor (ID: 288)"
    assert device_info.get("model") == "BMV-712"
    assert device_info.get("serial_number") == "HQ12345678"


async def test_map_device_info_no_manufacturer() -> None:
    """Test _map_device_info with no manufacturer."""
    mock_device = MagicMock(spec=VictronVenusDevice)
    mock_device.unique_id = "device_123"
    mock_device.manufacturer = None
    mock_device.name = "Unknown Device"
    mock_device.device_id = "0"
    mock_device.model = "Unknown"
    mock_device.serial_number = None

    installation_id = "12345"

    device_info = Hub._map_device_info(mock_device, installation_id)

    assert device_info.get("manufacturer") == "Victron Energy"
    assert (
        device_info.get("name") == "Unknown Device"
    )  # device_id == "0" uses name only


async def test_register_add_entities_callback(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test registering add entities callback."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)

    mock_callback = MagicMock()
    hub.register_new_metric_callback(MetricKind.SENSOR, mock_callback)

    assert MetricKind.SENSOR in hub.new_metric_callbacks
    assert hub.new_metric_callbacks[MetricKind.SENSOR] is mock_callback


async def test_unregister_add_entities_callback(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test unregistering add entities callback."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)

    # Register a callback first
    mock_callback = MagicMock()
    hub.register_new_metric_callback(MetricKind.SENSOR, mock_callback)

    # Verify it was registered
    assert MetricKind.SENSOR in hub.new_metric_callbacks
    assert hub.new_metric_callbacks[MetricKind.SENSOR] is mock_callback

    # Unregister the callback
    hub.unregister_all_new_metric_callbacks()

    # Verify it was removed
    assert MetricKind.SENSOR not in hub.new_metric_callbacks


async def test_on_new_metric_sensor(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test _on_new_metric callback."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    hub = Hub(hass, mock_config_entry)

    # Register callback that creates entities
    created_entities = []

    def mock_callback(device, metric, device_info):
        """Mock callback that creates a sensor entity."""
        entity = VictronSensor(device, metric, device_info)
        created_entities.append(entity)

    hub.register_new_metric_callback(MetricKind.SENSOR, mock_callback)

    # Create mock device and metric
    mock_device = MagicMock(spec=VictronVenusDevice)
    mock_device.unique_id = "device_123"
    mock_device.manufacturer = "Victron Energy"
    mock_device.name = "Test Device"
    mock_device.device_id = "288"
    mock_device.model = "Test Model"
    mock_device.serial_number = "HQ12345678"

    mock_metric = MagicMock(spec=VictronVenusMetric)
    mock_metric.metric_kind = MetricKind.SENSOR

    # Trigger the callback
    hub._on_new_metric(mock_victron_hub, mock_device, mock_metric)

    # Verify entity was created
    assert len(created_entities) == 1
    entity = created_entities[0]
    assert isinstance(entity, VictronSensor)

    # Patch schedule_update_ha_state and call _on_update_task
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule_update:
        # Call with a value that should trigger an update
        entity._on_update_task(42)
        mock_schedule_update.assert_called_once()
        assert entity._attr_native_value == 42

        # Call with same value that should not trigger an update
        entity._on_update_task(42)
        mock_schedule_update.assert_called_once()
        assert entity._attr_native_value == 42

        entity._on_update_task(100)
        assert mock_schedule_update.call_count == 2
        assert entity._attr_native_value == 100


async def test_hub_registers_stop_listener(
    hass: HomeAssistant, mock_config_entry, basic_config, mock_victron_hub
) -> None:
    """Test that hub registers a stop listener on initialization."""
    mock_config_entry.data = basic_config
    mock_config_entry.unique_id = "test_unique_id"

    # Create hub - it should register the stop listener
    _hub = Hub(hass, mock_config_entry)
    await _hub.start()

    # Fire the stop event to verify the listener was registered
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Verify disconnect was called when stop event fired
    mock_victron_hub.disconnect.assert_called_once()


async def test_victron_battery_sensor(
    snapshot: SnapshotAssertion, mqtt_test_setup
) -> None:
    """Test SENSOR MetricKind - battery current."""
    victron_hub, mock_async_add_entities = mqtt_test_setup
    mock_async_add_entities.reset_mock()

    # Inject a sensor metric (battery current)
    await inject_message(victron_hub, "N/123/battery/0/Dc/0/Current", '{"value": 10.5}')
    await finalize_injection(victron_hub)

    # Verify async_add_entities was called once
    assert mock_async_add_entities.call_count == 1
    call_args = mock_async_add_entities.call_args_list
    assert call_args == snapshot
