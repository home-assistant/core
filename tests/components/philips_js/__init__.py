"""Tests for the Philips TV integration."""

from typing import Any

MOCK_SERIAL_NO = "1234567890"
MOCK_NAME = "Philips TV"

MOCK_USERNAME = "mock_user"
MOCK_PASSWORD = "mock_password"
MOCK_HOSTNAME = "mock_hostname"

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
    "api_version": "1",
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

MOCK_RECORDINGS_LIST = {
    "version": "253.91",
    "recordings": [
        {
            "RecordingId": 36,
            "RecordingType": "RECORDING_ONGOING",
            "IsIpEpgRec": False,
            "ccid": 2091,
            "StartTime": 1676833531,
            "Duration": 569,
            "MarginStart": 0,
            "MarginEnd": 0,
            "EventId": 47369,
            "EITVersion": 0,
            "RetentionInfo": 0,
            "EventInfo": "This is a event info which is not rejected by codespell.",
            "EventExtendedInfo": "",
            "EventGenre": "8",
            "RecName": "Terra X",
            "SeriesID": "None",
            "SeasonNo": 0,
            "EpisodeNo": 0,
            "EpisodeCount": 72300,
            "ProgramNumber": 11110,
            "EventRating": 0,
            "hasDot": True,
            "isFTARecording": False,
            "LastPinChangedTime": 0,
            "Version": 344,
            "HasCicamPin": False,
            "HasLicenseFile": False,
            "Size": 0,
            "ResumeInfo": 0,
            "IsPartial": False,
            "AutoMarginStart": 0,
            "AutoMarginEnd": 0,
            "ServerRecordingId": -1,
            "ActualStartTime": 1676833531,
            "ProgramDuration": 0,
            "IsRadio": False,
            "EITSource": "EIT_SOURCE_PF",
            "RecError": "REC_ERROR_NONE",
        },
        {
            "RecordingId": 35,
            "RecordingType": "RECORDING_NEW",
            "IsIpEpgRec": False,
            "ccid": 2091,
            "StartTime": 1676832212,
            "Duration": 22,
            "MarginStart": 0,
            "MarginEnd": 0,
            "EventId": 47369,
            "EITVersion": 0,
            "RetentionInfo": -1,
            "EventInfo": (
                "This is another event info which is not rejected by codespell."
            ),
            "EventExtendedInfo": "",
            "EventGenre": "8",
            "RecName": "Terra X",
            "SeriesID": "None",
            "SeasonNo": 0,
            "EpisodeNo": 0,
            "EpisodeCount": 70980,
            "ProgramNumber": 11110,
            "EventRating": 0,
            "hasDot": True,
            "isFTARecording": False,
            "LastPinChangedTime": 0,
            "Version": 339,
            "HasCicamPin": False,
            "HasLicenseFile": False,
            "Size": 0,
            "ResumeInfo": 0,
            "IsPartial": False,
            "AutoMarginStart": 0,
            "AutoMarginEnd": 0,
            "ServerRecordingId": -1,
            "ActualStartTime": 1676832212,
            "ProgramDuration": 0,
            "IsRadio": False,
            "EITSource": "EIT_SOURCE_PF",
            "RecError": "REC_ERROR_NONE",
        },
        {
            "RecordingId": 34,
            "RecordingType": "RECORDING_PARTIALLY_VIEWED",
            "IsIpEpgRec": False,
            "ccid": 2091,
            "StartTime": 1676677580,
            "Duration": 484,
            "MarginStart": 0,
            "MarginEnd": 0,
            "EventId": -1,
            "EITVersion": 0,
            "RetentionInfo": -1,
            "EventInfo": (
                "\n\nAlpine Ski-WM: Parallel-Event,"
                " Übertragung aus Méribel/Frankreich"
                "\n\n14:10: Biathlon-WM (AD): 20 km Einzel"
                " Männer, Übertragung aus Oberhof"
                "\nHD-Produktion"
            ),
            "EventExtendedInfo": "",
            "EventGenre": "4",
            "RecName": "ZDF HD 2023-02-18 00:46",
            "SeriesID": "None",
            "SeasonNo": 0,
            "EpisodeNo": 0,
            "EpisodeCount": 2760,
            "ProgramNumber": 11110,
            "EventRating": 0,
            "hasDot": True,
            "isFTARecording": False,
            "LastPinChangedTime": 0,
            "Version": 328,
            "HasCicamPin": False,
            "HasLicenseFile": False,
            "Size": 0,
            "ResumeInfo": 56,
            "IsPartial": False,
            "AutoMarginStart": 0,
            "AutoMarginEnd": 0,
            "ServerRecordingId": -1,
            "ActualStartTime": 1676677581,
            "ProgramDuration": 0,
            "IsRadio": False,
            "EITSource": "EIT_SOURCE_PF",
            "RecError": "REC_ERROR_NONE",
        },
    ],
}

MOCK_MENU_ENTRY_ID = "01JZ41PCSDC1XDCC68AD3WTQ75"
MOCK_MENU_UNIQUE_ID = "123456"
MOCK_MENU_STORAGE_KEY = f"philips_js.{MOCK_MENU_ENTRY_ID}.menu"

MOCK_MENU_TOGGLE = {
    "node_id": 2,
    "type": "TOGGLE_NODE",
    "string_id": "org.droidtv.ui.strings.R.string.MAIN_TOGGLE",
    "data": {},
}
MOCK_MENU_TEXT = {
    "node_id": 3,
    "type": "TEXT_ENTRY",
    "string_id": "org.droidtv.ui.strings.R.string.MAIN_TEXT",
    "data": {},
}
# Named through its current value, like the parent menu around it
MOCK_MENU_SLIDER = {
    "node_id": 5,
    "type": "SLIDER_NODE",
    "data": {"slider_data": {"min": 0, "max": 100, "step_size": 1}},
}
MOCK_MENU_MULTI_SLIDER = {
    "node_id": 13,
    "type": "MULTIPLE_SLIDER",
    "string_id": "org.droidtv.ui.strings.R.string.MAIN_WHITE_POINT",
    "data": {
        "sliders": [
            {
                "slider_id": "org.droidtv.ui.strings.R.string.MAIN_RED",
                "slider_data": {"min": 0, "max": 255, "step_size": 1},
            },
            {
                "slider_id": "org.droidtv.ui.strings.R.string.MAIN_GREEN",
                "slider_data": {"min": 0, "max": 255, "step_size": 1},
            },
        ]
    },
}
MOCK_MENU_PICTURE = {
    "node_id": 4,
    "type": "PARENT_NODE",
    "context": "picture",
    "data": {"nodes": [MOCK_MENU_SLIDER, MOCK_MENU_MULTI_SLIDER]},
}
# Parent node with an active node, exposed as a select of its child nodes
MOCK_MENU_STYLE = {
    "node_id": 14,
    "type": "PARENT_NODE",
    "string_id": "org.droidtv.ui.strings.R.string.MAIN_STYLE",
    "data": {
        "nodes": [
            {
                "node_id": 15,
                "type": "PARENT_NODE",
                "string_id": "org.droidtv.ui.strings.R.string.MAIN_STYLE_VIVID",
                "data": {},
            },
            {
                "node_id": 16,
                "type": "PARENT_NODE",
                "string_id": "org.droidtv.ui.strings.R.string.MAIN_STYLE_NATURAL",
                "data": {},
            },
        ]
    },
}
# Nodes sharing a name, told apart by their first enum or their node id
MOCK_MENU_TIME_ZONES = [
    {
        "node_id": node_id,
        "type": "LIST_NODE",
        "string_id": "org.droidtv.ui.strings.R.string.MAIN_TIME_ZONE",
        "data": {
            "enums": [
                {"enum_id": enum_id, "string_id": enum_string_id}
                for enum_id, enum_string_id in enumerate(enum_string_ids)
            ]
        },
    }
    for node_id, enum_string_ids in (
        (
            6,
            (
                "org.droidtv.ui.strings.R.string.MAIN_QUEENSLAND",
                "org.droidtv.ui.strings.R.string.MAIN_VICTORIA",
            ),
        ),
        (7, ("org.droidtv.ui.strings.R.string.MAIN_AZORES",)),
    )
]
MOCK_MENU_SOUND_STYLES = [
    {
        "node_id": node_id,
        "type": "LIST_NODE",
        "string_id": "org.droidtv.ui.strings.R.string.MAIN_SOUND_STYLE",
        "data": {"enums": []},
    }
    for node_id in (8, 9)
]
# Nodes sharing both name and first enum, told apart by their node id
MOCK_MENU_INPUTS = [
    {
        "node_id": node_id,
        "type": "LIST_NODE",
        "string_id": "org.droidtv.ui.strings.R.string.MAIN_INPUT",
        "data": {
            "enums": [
                {"enum_id": 0, "string_id": "org.droidtv.ui.strings.R.string.MAIN_HDMI"}
            ]
        },
    }
    for node_id in (17, 18)
]
# Node without string id or name in its current value
MOCK_MENU_UNNAMED = {
    "node_id": 10,
    "type": "TOGGLE_NODE",
    "context": "unnamed",
    "data": {},
}
MOCK_MENU_ROOT = {
    "node_id": 1,
    "type": "PARENT_NODE",
    "string_id": "org.droidtv.ui.strings.R.string.MAIN_ROOT",
    "data": {
        "nodes": [
            MOCK_MENU_TOGGLE,
            MOCK_MENU_TEXT,
            MOCK_MENU_PICTURE,
            MOCK_MENU_STYLE,
            *MOCK_MENU_TIME_ZONES,
            *MOCK_MENU_SOUND_STYLES,
            *MOCK_MENU_INPUTS,
            MOCK_MENU_UNNAMED,
        ]
    },
}


def _mock_menu_value(node_id: int, data: dict, **kwargs: Any) -> dict:
    """Return a current value of a menu node."""
    return {
        "Nodeid": node_id,
        "Controllable": True,
        "Available": True,
        "data": data,
    } | kwargs


MOCK_MENU_CURRENT = {
    2: _mock_menu_value(2, {"value": True}),
    4: _mock_menu_value(4, {}, string_id="Picture"),
    5: _mock_menu_value(5, {"value": 50}, string_id="Brightness"),
    13: _mock_menu_value(
        13,
        {
            "values": [
                {"slider_id": "org.droidtv.ui.strings.R.string.MAIN_RED", "value": 127},
                {
                    "slider_id": "org.droidtv.ui.strings.R.string.MAIN_GREEN",
                    "value": 113,
                },
            ]
        },
    ),
    14: _mock_menu_value(14, {"activenode_id": 15}),
    6: _mock_menu_value(
        6,
        {
            "selected_item": 0,
            "enum_values": [
                {
                    "enum_id": 0,
                    "string_id": "org.droidtv.ui.strings.R.string.MAIN_QUEENSLAND",
                    "available": True,
                    "controllable": True,
                },
                {
                    "enum_id": 1,
                    "string_id": "org.droidtv.ui.strings.R.string.MAIN_VICTORIA",
                    "available": True,
                    "controllable": True,
                },
            ],
        },
    ),
}
MOCK_MENU_STRINGS = {
    "org.droidtv.ui.strings.R.string.MAIN_TOGGLE": "Toggle",
    "org.droidtv.ui.strings.R.string.MAIN_WHITE_POINT": "White point",
    "org.droidtv.ui.strings.R.string.MAIN_RED": "Red",
    "org.droidtv.ui.strings.R.string.MAIN_GREEN": "Green",
    "org.droidtv.ui.strings.R.string.MAIN_STYLE": "Style",
    "org.droidtv.ui.strings.R.string.MAIN_STYLE_VIVID": "Vivid",
    "org.droidtv.ui.strings.R.string.MAIN_STYLE_NATURAL": "Natural",
    "org.droidtv.ui.strings.R.string.MAIN_TIME_ZONE": "Time zone",
    "org.droidtv.ui.strings.R.string.MAIN_QUEENSLAND": "Queensland",
    "org.droidtv.ui.strings.R.string.MAIN_VICTORIA": "Victoria",
    "org.droidtv.ui.strings.R.string.MAIN_AZORES": "Azores",
    "org.droidtv.ui.strings.R.string.MAIN_SOUND_STYLE": "Sound style",
    "org.droidtv.ui.strings.R.string.MAIN_INPUT": "Input",
    "org.droidtv.ui.strings.R.string.MAIN_HDMI": "HDMI",
}
# The menu data cached from MOCK_MENU_ROOT, untranslated strings map to themselves
MOCK_MENU_DATA = {
    "structure": MOCK_MENU_ROOT,
    "strings": MOCK_MENU_STRINGS
    | {
        "org.droidtv.ui.strings.R.string.MAIN_ROOT": (
            "org.droidtv.ui.strings.R.string.MAIN_ROOT"
        ),
        "org.droidtv.ui.strings.R.string.MAIN_TEXT": (
            "org.droidtv.ui.strings.R.string.MAIN_TEXT"
        ),
    },
    "parent_node_ids": [14],
    "names": {"4": "Picture", "5": "Brightness"},
}
# Selected menu nodes, one of each entity type and one unknown to the TV
MOCK_MENU_SELECTED = [2, 99]
