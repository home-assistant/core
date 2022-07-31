"""Test config flow."""
from homeassistant import config_entries
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry


async def test_mqtt_abort_if_existing_entry(hass, mqtt_mock):
    """Check MQTT flow aborts when an entry already exist."""
    MockConfigEntry(domain="tasmota").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_MQTT}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_mqtt_abort_invalid_topic(hass, mqtt_mock):
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
    assert result["type"] == "abort"
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
    assert result["type"] == "abort"
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
    assert result["type"] == "form"


async def test_mqtt_setup(hass, mqtt_mock) -> None:
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
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "create_entry"
    assert result["result"].data == {"discovery_prefix": "tasmota/discovery"}


async def test_user_setup(hass, mqtt_mock):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "discovery_prefix": "tasmota/discovery",
    }


async def test_user_setup_advanced(hass, mqtt_mock):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "test_tasmota/discovery"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "discovery_prefix": "test_tasmota/discovery",
    }


async def test_user_setup_advanced_strip_wildcard(hass, mqtt_mock):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "test_tasmota/discovery/#"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "discovery_prefix": "test_tasmota/discovery",
    }


async def test_user_setup_invalid_topic_prefix(hass, mqtt_mock):
    """Test abort on invalid discovery topic."""
    result = await hass.config_entries.flow.async_init(
        "tasmota",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery_prefix": "tasmota/config/##"}
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_discovery_topic"


async def test_user_single_instance(hass, mqtt_mock):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="tasmota").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "tasmota", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
