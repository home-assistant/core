"""Test config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.typing import MqttMockHAClient


async def test_mqtt_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/DROP-1_C0FFEE/255",
        payload='{"devDesc":"Hub","devType":"hub","name":"Hub DROP-1_C0FFEE"}',
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result is not None
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "drop_command_topic": "drop_connect/DROP-1_C0FFEE/cmd/255",
        "drop_data_topic": "drop_connect/DROP-1_C0FFEE/data/255/#",
        "device_desc": "Hub",
        "device_id": "255",
        "name": "Hub DROP-1_C0FFEE",
        "device_type": "hub",
        "drop_hub_id": "DROP-1_C0FFEE",
        "drop_device_owner_id": "DROP-1_C0FFEE_255",
    }


async def test_duplicate(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/DROP-1_C0FFEE/255",
        payload='{"devDesc":"Hub","devType":"hub","name":"Hub DROP-1_C0FFEE"}',
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result is not None
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Attempting configuration of the same object should abort
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_incomplete_payload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/DROP-1_C0FFEE/255",
        payload='{"devDesc":"Hub"}',
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_bad_json(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/DROP-1_C0FFEE/255",
        payload="{BAD JSON}",
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_bad_topic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/FOO",
        payload=('{"devDesc":"Hub","devType":"hub","name":"Hub DROP-1_C0FFEE"}'),
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_no_payload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="drop_connect/discovery/DROP-1_C0FFEE/255",
        payload="",
        qos=0,
        retain=False,
        subscribed_topic="drop_connect/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "drop_connect",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test user setup."""
    result = await hass.config_entries.flow.async_init(
        "drop_connect", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
