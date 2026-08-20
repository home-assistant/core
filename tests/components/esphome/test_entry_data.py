"""Test ESPHome entry data."""

from unittest.mock import Mock, call, patch

from aioesphomeapi import (
    APIClient,
    DeviceInfo,
    EntityCategory as ESPHomeEntityCategory,
    EntityInfo,
    SensorInfo,
    SensorState,
    SerialProxyInfo,
    SerialProxyMode,
)
import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.const import CONF_NOISE_PSK
from homeassistant.components.esphome.entry_data import RuntimeEntryData
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery_flow, entity_registry as er
from homeassistant.helpers.service_info.esphome import ESPHomeServiceInfo

from .conftest import MockGenericDeviceEntryType


async def test_migrate_entity_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a legacy unique id is migrated to the version 3 format."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "11:22:33:44:55:AA-sensor-mysensor",
        suggested_object_id="my_sensor",
        disabled_by=None,
    )
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.my_sensor")
    assert state is not None
    assert state.state == "50"
    entry = entity_registry.async_get("sensor.my_sensor")
    assert entry is not None
    # The legacy unique id should have been renamed to the version 3 format,
    # keeping the entity (and its entity_id) instead of creating a new one
    assert entry.unique_id == "11:22:33:44:55:AA/0/sensor/my sensor"
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "11:22:33:44:55:AA-sensor-mysensor"
        )
        is None
    )


async def test_migrate_entity_unique_id_downgrade_upgrade(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test unique id migration prefers the original entity on downgrade upgrade."""
    # The original entity, already in the version 3 format
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "11:22:33:44:55:AA/0/sensor/my sensor",
        suggested_object_id="new_sensor",
        disabled_by=None,
    )
    # A duplicate left behind in the legacy format by a downgrade
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "11:22:33:44:55:AA-sensor-mysensor",
        suggested_object_id="old_sensor",
        disabled_by=None,
    )
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.new_sensor")
    assert state is not None
    assert state.state == "50"
    entry = entity_registry.async_get("sensor.new_sensor")
    assert entry is not None
    # Confirm we did not touch the legacy entity that was created
    # on downgrade so when they upgrade again they can delete the
    # entity that was only created on downgrade and they keep
    # the original one.
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "11:22:33:44:55:AA-sensor-mysensor"
        )
        is not None
    )
    assert entry.unique_id == "11:22:33:44:55:AA/0/sensor/my sensor"


async def test_discover_zwave() -> None:
    """Test ESPHome discovery of Z-Wave JS."""
    hass = Mock()
    # The noise PSK is read from the config entry, not the live client, so that
    # a dynamically provisioned key that could not be applied to the already
    # connected client is still passed on to the add-on.
    hass.config_entries.async_get_entry.return_value = Mock(
        data={CONF_NOISE_PSK: "mock-noise-psk"}
    )
    entry_data = RuntimeEntryData(
        "mock-id",
        "mock-title",
        Mock(
            connected_address="mock-client-address",
            port=1234,
            noise_psk=None,
        ),
        None,
    )
    device_info = DeviceInfo(
        name="mock-device-infoname",
        mac_address="mock-device-info-mac",
        zwave_proxy_feature_flags=1,
        zwave_home_id=1234,
    )

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        entry_data.async_on_connect(
            hass,
            device_info,
            None,
        )
        hass.config_entries.async_get_entry.assert_called_once_with("mock-id")
        mock_create_flow.assert_called_once_with(
            hass,
            "zwave_js",
            {"source": "esphome"},
            ESPHomeServiceInfo(
                name="mock-device-infoname",
                zwave_home_id=1234,
                ip_address="mock-client-address",
                port=1234,
                noise_psk="mock-noise-psk",
            ),
            discovery_key=discovery_flow.DiscoveryKey(
                domain="esphome",
                key="mock-device-info-mac",
                version=1,
            ),
        )


async def test_discover_zwave_without_home_id() -> None:
    """Test ESPHome does not start Z-Wave discovery without home ID."""
    hass = Mock()
    entry_data = RuntimeEntryData(
        "mock-id",
        "mock-title",
        Mock(
            connected_address="mock-client-address",
            port=1234,
            noise_psk=None,
        ),
        None,
    )
    device_info = DeviceInfo(
        name="mock-device-infoname",
        mac_address="mock-device-info-mac",
        zwave_proxy_feature_flags=1,
        zwave_home_id=0,  # No home ID (fresh adapter or unplugged)
    )

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        entry_data.async_on_connect(
            hass,
            device_info,
            None,
        )
        # Verify async_create_flow was NOT called when zwave_home_id is 0
        mock_create_flow.assert_not_called()


ZIGBEE_EXTENDED_PAN_ID = 0xD3B461708C2CF940


def _zigbee_device_info(
    *,
    zigbee_extended_pan_id: int = ZIGBEE_EXTENDED_PAN_ID,
    detected_mode: SerialProxyMode = SerialProxyMode.EZSP_ASH,
) -> DeviceInfo:
    """Return device info for a device proxying a Zigbee radio and two RS-232 ports."""
    return DeviceInfo(
        name="mock-device-infoname",
        mac_address="mock-device-info-mac",
        zigbee_proxy_feature_flags=1,
        zigbee_extended_pan_id=zigbee_extended_pan_id,
        serial_proxies=[
            SerialProxyInfo(name="RS-232 Port 1", baud_rate=9600),
            SerialProxyInfo(
                name="Zigbee", detected_mode=detected_mode, baud_rate=460800
            ),
            SerialProxyInfo(name="RS-232 Port 2", baud_rate=9600),
        ],
    )


@pytest.mark.parametrize(
    "zigbee_extended_pan_id",
    [
        pytest.param(ZIGBEE_EXTENDED_PAN_ID, id="network_formed"),
        # A radio that has no network yet is still a radio worth setting up
        pytest.param(0, id="no_network_formed"),
    ],
)
async def test_discover_zigbee(zigbee_extended_pan_id: int) -> None:
    """Test ESPHome discovery of ZHA."""
    hass = Mock()
    hass.config_entries.async_get_entry.return_value = Mock(
        data={CONF_NOISE_PSK: "mock-noise-psk"}
    )
    entry_data = RuntimeEntryData(
        "mock-id",
        "mock-title",
        Mock(
            connected_address="mock-client-address",
            port=1234,
            noise_psk=None,
        ),
        None,
    )

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        entry_data.async_on_connect(
            hass,
            _zigbee_device_info(zigbee_extended_pan_id=zigbee_extended_pan_id),
            None,
        )

    assert mock_create_flow.mock_calls == [
        call(
            hass,
            "zha",
            {"source": "esphome"},
            ESPHomeServiceInfo(
                name="mock-device-infoname",
                zwave_home_id=None,
                ip_address="mock-client-address",
                port=1234,
                noise_psk="mock-noise-psk",
                zigbee_extended_pan_id=zigbee_extended_pan_id,
                serial_port_name="Zigbee",
                serial_port_baudrate=460800,
            ),
            discovery_key=discovery_flow.DiscoveryKey(
                domain="esphome",
                key="mock-device-info-mac",
                version=1,
            ),
        )
    ]


async def test_discover_zigbee_without_detected_radio() -> None:
    """Test ESPHome does not start ZHA discovery until a radio is detected."""
    hass = Mock()
    entry_data = RuntimeEntryData(
        "mock-id",
        "mock-title",
        Mock(
            connected_address="mock-client-address",
            port=1234,
            noise_psk=None,
        ),
        None,
    )

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        entry_data.async_on_connect(
            hass,
            # The tap has not gotten an answer out of the port, so what is behind it -- a
            # Zigbee radio, a Z-Wave one, nothing at all -- is still unknown
            _zigbee_device_info(detected_mode=SerialProxyMode.RAW),
            None,
        )

    assert len(mock_create_flow.mock_calls) == 0


async def test_unknown_entity_type_skipped(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unknown entity types are skipped gracefully."""

    class UnknownInfo(EntityInfo):
        """Mock unknown entity info type."""

    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
        ),
        UnknownInfo(
            object_id="unknown",
            key=2,
            name="unknown entity",
        ),
    ]
    states = [SensorState(key=1, state=42)]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    assert "UnknownInfo" in caplog.text
    assert "not supported in this version of Home Assistant" in caplog.text

    # Known entity still works
    state = hass.states.get("sensor.test_my_sensor")
    assert state is not None
    assert state.state == "42"
