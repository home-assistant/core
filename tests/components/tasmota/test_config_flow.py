"""Test config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


async def test_mqtt_abort_if_existing_entry(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Check MQTT flow aborts when an entry already exist."""
    MockConfigEntry(domain="tasmota").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_mqtt_abort_invalid_topic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Check MQTT flow aborts if discovery topic is invalid."""
    discovery_info = MqttServiceInfo(
        topic="tasmota/discovery/DC4F220848A2/bla",
        payload=(
            '{"ip":"192.168.0.136","dn":"Tasmota","fn":["Tasmota",null,null,null,null,'
            'null,null,null],"hn":"tasmota_0848A2","mac":"DC4F220848A2","md":"Sonoff Basic",'
            '"ty":0,"if":0,"ofln":"Offline","onln":"Online","state":["OFF","ON",'
            '"TOGGLE","HOLD"],"sw":"9.4.0.4","t":"tasmota_0848A2","ft":"%topic%/%prefix%/",'
            '"tp":["cmnd","stat","tele"],"rl":[1,0,0,0,0,0,0,0],"swc":[-1,-1,-1,-1,-1,-1,-1,-1],'
            '"swn":[null,null,null,null,null,null,null,null],"btn":[0,0,0,0,0,0,0,0],'
            '"so":{"4":0,"11":0,"13":0,"17":1,"20":0,"30":0,"68":0,"73":0,"82":0,"114":1,"117":0},'
            '"lk":1,"lt_st":0,"sho":[0,0,0,0],"ver":1}'
        ),
        qos=0,
        retain=False,
        subscribed_topic="tasmota/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"

    discovery_info = MqttServiceInfo(
        topic="tasmota/discovery/DC4F220848A2/config",
        payload="",
        qos=0,
        retain=False,
        subscribed_topic="tasmota/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"

    discovery_info = MqttServiceInfo(
        topic="tasmota/discovery/DC4F220848A2/config",
        payload=(
            '{"ip":"192.168.0.136","dn":"Tasmota","fn":["Tasmota",null,null,null,null,'
            'null,null,null],"hn":"tasmota_0848A2","mac":"DC4F220848A2","md":"Sonoff Basic",'
            '"ty":0,"if":0,"ofln":"Offline","onln":"Online","state":["OFF","ON",'
            '"TOGGLE","HOLD"],"sw":"9.4.0.4","t":"tasmota_0848A2","ft":"%topic%/%prefix%/",'
            '"tp":["cmnd","stat","tele"],"rl":[1,0,0,0,0,0,0,0],"swc":[-1,-1,-1,-1,-1,-1,-1,-1],'
            '"swn":[null,null,null,null,null,null,null,null],"btn":[0,0,0,0,0,0,0,0],'
            '"so":{"4":0,"11":0,"13":0,"17":1,"20":0,"30":0,"68":0,"73":0,"82":0,"114":1,"117":0},'
            '"lk":1,"lt_st":0,"sho":[0,0,0,0],"ver":1}'
        ),
        qos=0,
        retain=False,
        subscribed_topic="tasmota/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM


async def test_mqtt_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test we can finish a config flow through MQTT with custom prefix."""
    discovery_info = MqttServiceInfo(
        topic="tasmota/discovery/DC4F220848A2/config",
        payload=(
            '{"ip":"192.168.0.136","dn":"Tasmota","fn":["Tasmota",null,null,null,null,'
            'null,null,null],"hn":"tasmota_0848A2","mac":"DC4F220848A2","md":"Sonoff Basic",'
            '"ty":0,"if":0,"ofln":"Offline","onln":"Online","state":["OFF","ON",'
            '"TOGGLE","HOLD"],"sw":"9.4.0.4","t":"tasmota_0848A2","ft":"%topic%/%prefix%/",'
            '"tp":["cmnd","stat","tele"],"rl":[1,0,0,0,0,0,0,0],"swc":[-1,-1,-1,-1,-1,-1,-1,-1],'
            '"swn":[null,null,null,null,null,null,null,null],"btn":[0,0,0,0,0,0,0,0],'
            '"so":{"4":0,"11":0,"13":0,"17":1,"20":0,"30":0,"68":0,"73":0,"82":0,"114":1,"117":0},'
            '"lk":1,"lt_st":0,"sho":[0,0,0,0],"ver":1}'
        ),
        qos=0,
        retain=False,
        subscribed_topic="tasmota/discovery/#",
        timestamp=None,
    )
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {"discovery_prefix": "tasmota/discovery"}


async def test_user_setup(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "discovery_prefix": "tasmota/discovery",
    }


async def test_user_setup_advanced(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "test_tasmota/discovery"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "discovery_prefix": "test_tasmota/discovery",
    }


async def test_user_setup_advanced_strip_wildcard(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "test_tasmota/discovery/#"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "discovery_prefix": "test_tasmota/discovery",
    }


async def test_user_setup_invalid_topic_prefix(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test abort on invalid discovery topic."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "tasmota/config/##"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_discovery_topic"


async def test_user_single_instance(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="tasmota").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
