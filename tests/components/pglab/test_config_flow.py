"""Test the PG LAB Electronics config flow."""

from homeassistant.components.mqtt import MQTT_CONNECTION_STATE
from homeassistant.components.pglab.const import DOMAIN
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
    """Test MQTT flow aborts when an entry already exist."""

    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}
    )

    # Be sure that result is abort. Only single instance is allowed.
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_mqtt_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="pglab/discovery/E-Board-DD53AC85/config",
        payload=(
            '{"ip":"192.168.1.16", "mac":"80:34:28:1B:18:5A", "name":"e-board-office",'
            '"hw":"255.255.255", "fw":"255.255.255", "type":"E-Board", "id":"E-Board-DD53AC85",'
            '"manufacturer":"PG LAB Electronics", "params":{"shutters":0, "boards":"10000000" } }'
        ),
        qos=0,
        retain=False,
        subscribed_topic="pglab/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].data == {"discovery_prefix": "pglab/discovery"}


async def test_mqtt_abort_invalid_topic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Check MQTT flow aborts if discovery topic is invalid."""
    discovery_info = MqttServiceInfo(
        topic="pglab/discovery/E-Board-DD53AC85/wrong_topic",
        payload=(
            '{"ip":"192.168.1.16", "mac":"80:34:28:1B:18:5A", "name":"e-board-office",'
            '"hw":"255.255.255", "fw":"255.255.255", "type":"E-Board", "id":"E-Board-DD53AC85",'
            '"manufacturer":"PG LAB Electronics", "params":{"shutters":0, "boards":"10000000" } }'
        ),
        qos=0,
        retain=False,
        subscribed_topic="pglab/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"

    discovery_info = MqttServiceInfo(
        topic="pglab/discovery/E-Board-DD53AC85/config",
        payload="",
        qos=0,
        retain=False,
        subscribed_topic="pglab/discovery/#",
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
    assert result["result"].data == {
        "discovery_prefix": "pglab/discovery",
    }


async def test_user_setup_mqtt_not_connected(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that the user setup is aborted when MQTT is not connected."""

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_connected"


async def test_user_setup_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test that the user setup is aborted when MQTT is not configured."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"
