"""Constants for the samsungtv tests."""

from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
    DOMAIN,
    ENCRYPTED_WEBSOCKET_PORT,
    LEGACY_PORT,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    WEBSOCKET_SSL_PORT,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from tests.common import load_json_object_fixture

ENTRYDATA_LEGACY = {
    CONF_HOST: "10.10.12.34",
    CONF_PORT: LEGACY_PORT,
    CONF_METHOD: METHOD_LEGACY,
}
ENTRYDATA_ENCRYPTED_WEBSOCKET = {
    CONF_HOST: "10.10.12.34",
    CONF_PORT: ENCRYPTED_WEBSOCKET_PORT,
    CONF_METHOD: METHOD_ENCRYPTED_WEBSOCKET,
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
    CONF_TOKEN: "037739871315caef138547b03e348b72",
    CONF_SESSION_ID: "2",
}
ENTRYDATA_WEBSOCKET = {
    CONF_HOST: "10.10.12.34",
    CONF_METHOD: METHOD_WEBSOCKET,
    CONF_PORT: WEBSOCKET_SSL_PORT,
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
    CONF_MODEL: "UE43LS003",
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

MOCK_SSDP_DATA = SsdpServiceInfo(
    **load_json_object_fixture("ssdp_service_remote_control_receiver.json", DOMAIN)
)

MOCK_SSDP_DATA_RENDERING_CONTROL_ST = SsdpServiceInfo(
    **load_json_object_fixture("ssdp_service_rendering_control.json", DOMAIN)
)

MOCK_SSDP_DATA_MAIN_TV_AGENT_ST = SsdpServiceInfo(
    **load_json_object_fixture("ssdp_device_main_tv_agent.json", DOMAIN)
)
