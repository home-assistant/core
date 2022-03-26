"""Tests for the Philips TV integration."""

MOCK_SERIAL_NO = "1234567890"
MOCK_NAME = "Philips TV"

MOCK_USERNAME = "mock_user"
MOCK_PASSWORD = "mock_password"

MOCK_SYSTEM = {
    "menulanguage": "English",
    "name": MOCK_NAME,
    "country": "Sweden",
    "serialnumber": MOCK_SERIAL_NO,
    "softwareversion": "abcd",
    "model": "modelname",
}

MOCK_SYSTEM_UNPAIRED = {
    "menulanguage": "Dutch",
    "name": "55PUS7181/12",
    "country": "Netherlands",
    "serialnumber": "ABCDEFGHIJKLF",
    "softwareversion": "TPM191E_R.101.001.208.001",
    "model": "65OLED855/12",
    "deviceid": "1234567890",
    "nettvversion": "6.0.2",
    "epgsource": "one",
    "api_version": {"Major": 6, "Minor": 2, "Patch": 0},
    "featuring": {
        "jsonfeatures": {
            "editfavorites": ["TVChannels", "SatChannels"],
            "recordings": ["List", "Schedule", "Manage"],
            "ambilight": ["LoungeLight", "Hue", "Ambilight"],
            "menuitems": ["Setup_Menu"],
            "textentry": [
                "context_based",
                "initial_string_available",
                "editor_info_available",
            ],
            "applications": ["TV_Apps", "TV_Games", "TV_Settings"],
            "pointer": ["not_available"],
            "inputkey": ["key"],
            "activities": ["intent"],
            "channels": ["preset_string"],
            "mappings": ["server_mapping"],
        },
        "systemfeatures": {
            "tvtype": "consumer",
            "content": ["dmr", "dms_tad"],
            "tvsearch": "intent",
            "pairing_type": "digest_auth_pairing",
            "secured_transport": "True",
        },
    },
}

MOCK_USERINPUT = {
    "host": "1.1.1.1",
}

MOCK_CONFIG = {
    "host": "1.1.1.1",
    "api_version": 1,
    "system": MOCK_SYSTEM,
}

MOCK_CONFIG_PAIRED = {
    "host": "1.1.1.1",
    "api_version": 6,
    "username": MOCK_USERNAME,
    "password": MOCK_PASSWORD,
    "system": MOCK_SYSTEM_UNPAIRED,
}

MOCK_ENTITY_ID = "media_player.philips_tv"
