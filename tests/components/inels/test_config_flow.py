"""Test the iNELS config flow."""

from homeassistant.components.inels.const import DOMAIN, TITLE
from homeassistant.components.mqtt import MQTT_CONNECTION_STATE
from homeassistant.config_entries import SOURCE_MQTT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


async def test_mqtt_config_single_instance(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """The MQTT test flow is aborted if an entry already exists."""

    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_mqtt_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """When an MQTT message is received on the discovery topic, it triggers a config flow."""
    discovery_info = MqttServiceInfo(
        topic="inels/status/MAC_ADDRESS/gw",
        payload='{"CUType":"CU3-08M","Status":"Runfast","FW":"02.97.18"}',
        qos=0,
        retain=False,
        subscribed_topic="inels/status/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["result"].data == {}


async def test_mqtt_abort_invalid_topic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Check MQTT flow aborts if discovery topic is invalid."""
    discovery_info = MqttServiceInfo(
        topic="inels/status/MAC_ADDRESS/wrong_topic",
        payload='{"CUType":"CU3-08M","Status":"Runfast","FW":"02.97.18"}',
        qos=0,
        retain=False,
        subscribed_topic="inels/status/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_abort_empty_payload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Check MQTT flow aborts if discovery payload is empty."""
    discovery_info = MqttServiceInfo(
        topic="inels/status/MAC_ADDRESS/gw",
        payload="",
        qos=0,
        retain=False,
        subscribed_topic="inels/status/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_user_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test if the user can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["result"].data == {}


async def test_user_config_single_instance(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """The user test flow is aborted if an entry already exists."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_setup_mqtt_not_connected(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """The user setup test flow is aborted when MQTT is not connected."""

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_connected"


async def test_user_setup_mqtt_not_configured(hass: HomeAssistant) -> None:
    """The user setup test flow is aborted when MQTT is not configured."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"
