"""Test Axis device."""

from collections.abc import Callable
from ipaddress import ip_address
from types import MappingProxyType
from typing import Any
from unittest import mock
from unittest.mock import ANY, Mock, call, patch

import axis as axislib
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import axis
from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import RtspEventMock, RtspStateType
from .const import (
    API_DISCOVERY_BASIC_DEVICE_INFO,
    API_DISCOVERY_MQTT,
    FORMATTED_MAC,
    MAC,
    NAME,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    "api_discovery_items", [({}), (API_DISCOVERY_BASIC_DEVICE_INFO)]
)
async def test_device_registry_entry(
    config_entry_setup: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Successful setup."""
    device_entry = device_registry.async_get_device(
        identifiers={(AXIS_DOMAIN, config_entry_setup.unique_id)}
    )
    assert device_entry == snapshot


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_MQTT])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_support_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Successful setup."""
    mqtt_call = call(f"axis/{MAC}/#", mock.ANY, 0, "utf-8", ANY)
    assert mqtt_call in mqtt_mock.async_subscribe.call_args_list

    topic = f"axis/{MAC}/event/tns:onvif/Device/tns:axis/Sensor/PIR/$source/sensor/0"
    message = (
        b'{"timestamp": 1590258472044, "topic": "onvif:Device/axis:Sensor/PIR",'
        b' "message": {"source": {"sensor": "0"}, "key": {}, "data": {"state": "1"}}}'
    )

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
    async_fire_mqtt_message(hass, topic, message)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1

    pir = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0")
    assert pir.state == STATE_ON
    assert pir.name == f"{NAME} PIR 0"


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_MQTT])
@pytest.mark.parametrize("mqtt_status_code", [401])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_support_mqtt_low_privilege(mqtt_mock: MqttMockHAClient) -> None:
    """Successful setup."""
    mqtt_call = call(f"{MAC}/#", mock.ANY, 0, "utf-8")
    assert mqtt_call not in mqtt_mock.async_subscribe.call_args_list


async def test_update_address(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_requests: Callable[[str], None],
) -> None:
    """Test update address works."""
    hub = config_entry_setup.runtime_data
    assert hub.api.config.host == "1.2.3.4"

    mock_requests("2.3.4.5")
    await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data=ZeroconfServiceInfo(
            ip_address=ip_address("2.3.4.5"),
            ip_addresses=[ip_address("2.3.4.5")],
            hostname="mock_hostname",
            name="name",
            port=80,
            properties={"macaddress": MAC},
            type="mock_type",
        ),
        context={"source": SOURCE_ZEROCONF},
    )
    await hass.async_block_till_done()

    assert hub.api.config.host == "2.3.4.5"


@pytest.mark.usefixtures("config_entry_setup")
async def test_device_unavailable(
    hass: HomeAssistant,
    mock_rtsp_event: RtspEventMock,
    mock_rtsp_signal_state: RtspStateType,
) -> None:
    """Successful setup."""
    # Provide an entity that can be used to verify connection state on
    mock_rtsp_event(
        topic="tns1:AudioSource/tnsaxis:TriggerLevel",
        data_type="triggered",
        data_value="10",
        source_name="channel",
        source_idx="1",
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state == STATE_OFF

    # Connection to device has failed

    mock_rtsp_signal_state(connected=False)
    await hass.async_block_till_done()

    assert (
        hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state
        == STATE_UNAVAILABLE
    )

    # Connection to device has been restored

    mock_rtsp_signal_state(connected=True)
    await hass.async_block_till_done()

    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state == STATE_OFF


@pytest.mark.usefixtures("mock_default_requests")
async def test_device_trigger_reauth_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    config_entry.add_to_hass(hass)
    with (
        patch.object(
            axis, "get_axis_api", side_effect=axis.errors.AuthenticationRequired
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_flow_init.assert_called_once()
    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_shutdown(config_entry_data: MappingProxyType[str, Any]) -> None:
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = config_entry_data

    mock_api = Mock()
    mock_api.vapix.serial_number = FORMATTED_MAC
    axis_device = axis.hub.AxisHub(hass, entry, mock_api)

    await axis_device.shutdown(None)

    assert len(axis_device.api.stream.stop.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        # Device unauthorized yields authentication required error
        (axislib.Unauthorized, ConfigEntryState.SETUP_ERROR),
        # Device unavailable yields cannot connect error
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (axislib.RequestError, ConfigEntryState.SETUP_RETRY),
        # Device yield unknown error
        (axislib.AxisException, ConfigEntryState.SETUP_ERROR),
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_get_axis_api_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Failed setup schedules a retry of setup."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.axis.hub.api.axis.interfaces.vapix.Vapix.initialize",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state == state
