"""Tests for the Philips TV integration."""

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
            "EventInfo": "This is another event info which is not rejected by codespell.",
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
            "EventInfo": "\n\nAlpine Ski-WM: Parallel-Event, Übertragung aus Méribel/Frankreich\n\n14:10: Biathlon-WM (AD): 20 km Einzel Männer, Übertragung aus Oberhof\nHD-Produktion",
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
