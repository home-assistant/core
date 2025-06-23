"""Test Droplet config flow."""

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.typing import MqttMockHAClient

TEST_SUBSCRIBED_TOPIC = "droplet/discovery/#"


async def configure_device_id(hass: HomeAssistant, device_id: str) -> ConfigFlowResult:
    """Configure a mock device with a given device ID."""
    discovery_info = MqttServiceInfo(
        topic="droplet/discovery/ABCD",
        payload=f'{{"dev": {{"ids":"droplet-{device_id}", "mdl":"Droplet 1.0", "mf":"Hydrific, part of LIXIL",'
        f'"sw": "0.6.0", "sn": "{device_id}"}}, "state_topic": "droplet-{device_id}/state", "availability_topic":'
        f'"droplet-{device_id}/health"}}',
        qos=0,
        retain=False,
        subscribed_topic=TEST_SUBSCRIBED_TOPIC,
        timestamp=None,
    )
    return await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )


async def test_mqtt_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test a normal config flow."""
    result = await configure_device_id(hass, "ABCD")
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
        "droplet_data_topic": "droplet-ABCD/state",
        "droplet_health_topic": "droplet-ABCD/health",
        "device_id": "droplet-ABCD",
        "device_name": "Droplet",
        "device_manufacturer": "Hydrific, part of LIXIL",
        "device_model": "Droplet 1.0",
        "device_sw": "0.6.0",
        "device_sn": "ABCD",
    }


async def test_mqtt_setup_bad_json(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a config flow with invalid JSON."""
    discovery_info = MqttServiceInfo(
        topic="droplet/discovery/ABCD",
        payload="lkjdsjlkdsf",
        qos=0,
        retain=False,
        subscribed_topic=TEST_SUBSCRIBED_TOPIC,
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_topic_mismatch(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a config flow with an inappropriate topic."""
    discovery_info = MqttServiceInfo(
        topic="droplet/discovery/ABCD",
        payload='{"dev": {"ids":"droplet-ABCD", "mdl":"Droplet 1.0", "mf":"Hydrific, part of LIXIL",'
        '"sw": "0.6.0", "sn": "ABCD"}, "state_topic": "droplet-EFGH/state", "availability_topic":'
        '"droplet-ABCD/health"}',
        qos=0,
        retain=False,
        subscribed_topic=TEST_SUBSCRIBED_TOPIC,
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_setup_duplicate_device(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test setting up a duplicate device."""
    # Configure a device as normal
    result = await configure_device_id(hass, "ABCD")
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result is not None

    # Now try to configure the same device again
    result = await configure_device_id(hass, "ABCD")
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_setup_user(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test that user setup aborts."""
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_USER},
    )
    assert result is not None
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
