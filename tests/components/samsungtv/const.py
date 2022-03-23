"""Constants for the samsungtv tests."""
from homeassistant.components.samsungtv.const import CONF_SESSION_ID
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)

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

SAMPLE_APP_LIST = [
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

SAMPLE_DEVICE_INFO_WIFI = {
    "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
    "device": {
        "modelName": "82GXARRS",
        "wifiMac": "aa:bb:ww:ii:ff:ii",
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
        "wifiMac": "aa:bb:ww:ii:ff:ii",
        "developerMode": "0",
        "developerIP": "",
    },
    "type": "Samsung SmartTV",
    "uri": "https://1.2.3.4:8002/api/v2/",
}
