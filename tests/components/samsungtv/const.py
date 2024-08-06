"""Constants for the samsungtv tests."""

from samsungtvws.event import ED_INSTALLED_APP_EVENT

from homeassistant.components import ssdp
from homeassistant.components.samsungtv.const import (
    CONF_SESSION_ID,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
)
from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
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

MOCK_SSDP_DATA_RENDERING_CONTROL_ST = ssdp.SsdpServiceInfo(
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
MOCK_SSDP_DATA_MAIN_TV_AGENT_ST = ssdp.SsdpServiceInfo(
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

SAMPLE_DEVICE_INFO_FRAME = {
    "device": {
        "FrameTVSupport": "true",
        "GamePadSupport": "true",
        "ImeSyncedSupport": "true",
        "OS": "Tizen",
        "TokenAuthSupport": "true",
        "VoiceSupport": "true",
        "countryCode": "FR",
        "description": "Samsung DTV RCR",
        "developerIP": "0.0.0.0",
        "developerMode": "0",
        "duid": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
        "firmwareVersion": "Unknown",
        "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
        "ip": "1.2.3.4",
        "model": "17_KANTM_UHD",
        "modelName": "UE43LS003",
        "name": "[TV] Samsung Frame (43)",
        "networkType": "wired",
        "resolution": "3840x2160",
        "smartHubAgreement": "true",
        "type": "Samsung SmartTV",
        "udn": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
        "wifiMac": "aa:ee:tt:hh:ee:rr",
    },
    "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
    "isSupport": (
        '{"DMP_DRM_PLAYREADY":"false","DMP_DRM_WIDEVINE":"false","DMP_available":"true",'
        '"EDEN_available":"true","FrameTVSupport":"true","ImeSyncedSupport":"true",'
        '"TokenAuthSupport":"true","remote_available":"true","remote_fourDirections":"true",'
        '"remote_touchPad":"true","remote_voiceControl":"true"}\n'
    ),
    "name": "[TV] Samsung Frame (43)",
    "remote": "1.0",
    "type": "Samsung SmartTV",
    "uri": "https://1.2.3.4:8002/api/v2/",
    "version": "2.0.25",
}

SAMPLE_DEVICE_INFO_UE48JU6400 = {
    "id": "uuid:223da676-497a-4e06-9507-5e27ec4f0fb3",
    "name": "[TV] TV-UE48JU6470",
    "version": "2.0.25",
    "device": {
        "type": "Samsung SmartTV",
        "duid": "uuid:223da676-497a-4e06-9507-5e27ec4f0fb3",
        "model": "15_HAWKM_UHD_2D",
        "modelName": "UE48JU6400",
        "description": "Samsung DTV RCR",
        "networkType": "wired",
        "ssid": "",
        "ip": "1.2.3.4",
        "firmwareVersion": "Unknown",
        "name": "[TV] TV-UE48JU6470",
        "id": "uuid:223da676-497a-4e06-9507-5e27ec4f0fb3",
        "udn": "uuid:223da676-497a-4e06-9507-5e27ec4f0fb3",
        "resolution": "1920x1080",
        "countryCode": "AT",
        "msfVersion": "2.0.25",
        "smartHubAgreement": "true",
        "wifiMac": "aa:bb:aa:aa:aa:aa",
        "developerMode": "0",
        "developerIP": "",
    },
    "type": "Samsung SmartTV",
    "uri": "https://1.2.3.4:8002/api/v2/",
}

SAMPLE_EVENT_ED_INSTALLED_APP = {
    "event": ED_INSTALLED_APP_EVENT,
    "from": "host",
    "data": {
        "data": [
            {
                "appId": "111299001912",
                "app_type": 2,
                "icon": "/opt/share/webappservice/apps_icon/FirstScreen/111299001912/250x250.png",
                "is_lock": 0,
                "name": "YouTube",
            },
            {
                "appId": "3201608010191",
                "app_type": 2,
                "icon": "/opt/share/webappservice/apps_icon/FirstScreen/3201608010191/250x250.png",
                "is_lock": 0,
                "name": "Deezer",
            },
            {
                "appId": "3201606009684",
                "app_type": 2,
                "icon": "/opt/share/webappservice/apps_icon/FirstScreen/3201606009684/250x250.png",
                "is_lock": 0,
                "name": "Spotify - Music and Podcasts",
            },
        ]
    },
}
