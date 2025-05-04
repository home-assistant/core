"""Constants for the samsungtv tests."""

from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
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
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

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

MOCK_SSDP_DATA_RENDERING_CONTROL_ST = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="urn:schemas-upnp-org:service:RenderingControl:1",
    ssdp_location="https://fake_host:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
    },
)
MOCK_SSDP_DATA_MAIN_TV_AGENT_ST = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="urn:samsung.com:service:MainTVAgent2:1",
    ssdp_location="https://fake_host:12345/tv_agent",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "[TV] fake_name",
        ATTR_UPNP_MANUFACTURER: "Samsung fake_manufacturer",
        ATTR_UPNP_MODEL_NAME: "fake_model",
        ATTR_UPNP_UDN: "uuid:0d1cef00-00dc-1000-9c80-4844f7b172de",
    },
)

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
