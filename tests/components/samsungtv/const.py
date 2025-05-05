"""Constants for the samsungtv tests."""

from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
    DOMAIN,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from tests.common import load_json_object_fixture

MOCK_CONFIG = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake",
    CONF_PORT: 55000,
    CONF_METHOD: METHOD_LEGACY,
}
MOCK_CONFIG_ENCRYPTED_WS = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake",
    CONF_PORT: 8000,
}
MOCK_ENTRYDATA_ENCRYPTED_WS = {
    **MOCK_CONFIG_ENCRYPTED_WS,
    CONF_IP_ADDRESS: "test",
    CONF_METHOD: "encrypted",
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
    CONF_TOKEN: "037739871315caef138547b03e348b72",
    CONF_SESSION_ID: "2",
}
MOCK_ENTRYDATA_WS = {
    CONF_HOST: "fake_host",
    CONF_METHOD: METHOD_WEBSOCKET,
    CONF_PORT: 8002,
    CONF_MODEL: "any",
    CONF_NAME: "any",
}
MOCK_ENTRY_WS_WITH_MAC = {
    CONF_IP_ADDRESS: "test",
    CONF_HOST: "fake_host",
    CONF_METHOD: "websocket",
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
    CONF_NAME: "fake",
    CONF_PORT: 8002,
    CONF_TOKEN: "123456789",
}


SAMPLE_DEVICE_INFO_WIFI = {
    "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
    "device": {
        "modelName": "82GXARRS",
        "wifiMac": "aa:bb:aa:aa:aa:aa",
        "name": "[TV] Living Room",
        "type": "Samsung SmartTV",
        "networkType": "wireless",
    },
}


MOCK_SSDP_DATA_RENDERING_CONTROL_ST = SsdpServiceInfo(
    **load_json_object_fixture("ssdp_service_rendering_control.json", DOMAIN)
)

MOCK_SSDP_DATA_MAIN_TV_AGENT_ST = SsdpServiceInfo(
    **load_json_object_fixture("ssdp_device_main_tv_agent.json", DOMAIN)
)
