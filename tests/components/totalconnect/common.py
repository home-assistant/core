"""Common methods used across tests for TotalConnect."""

import copy
from typing import Any
from unittest.mock import patch

import jwt
import requests_mock
from total_connect_client import ArmingState, ZoneStatus, ZoneType
from total_connect_client.const import (
    AUTH_CONFIG_ENDPOINT,
    AUTH_TOKEN_ENDPOINT,
    HTTP_API_SESSION_DETAILS_ENDPOINT,
    make_http_endpoint,
)

from homeassistant.components.totalconnect.const import (
    AUTO_BYPASS,
    CODE_REQUIRED,
    CONF_USERCODES,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

LOCATION_ID = 1234567

USERNAME = "username@me.com"
PASSWORD = "password"
USERCODES = {LOCATION_ID: "7890"}
CONFIG_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_USERCODES: USERCODES,
}
CONFIG_DATA_NO_USERCODES = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}

OPTIONS_DATA = {AUTO_BYPASS: False, CODE_REQUIRED: False}
OPTIONS_DATA_CODE_REQUIRED = {AUTO_BYPASS: False, CODE_REQUIRED: True}

TOTALCONNECT_GET_CONFIG = (
    "homeassistant.components.totalconnect.TotalConnectClient._get_configuration"
)
TOTALCONNECT_REQUEST_TOKEN = (
    "homeassistant.components.totalconnect.TotalConnectClient._request_token"
)

LOCATION_NAME = "test"
SECURITY_DEVICE_ID = 7654321
USER_ID = 9876543

REST_RESULT_CONFIG = {
    "RevisionNumber": "1.2.3",
    "version": "0.0.4",
    "AppConfig": [
        {
            "tc2APIKey": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA6bdkwTazBVt7eIcelDFcfojTC4XwDAfmvVJq9EdjyCa7neeow4tfoWe57oLPkjw+Ge5VEgUOus7aqhywKBTwlmlGUiTpQLUtVuxmam2nG3kvbKA2T6HbWKQfrJsdGitZLgwOIfzjDrIFTUjRiTIV8CYO8rmsLtaQUE20PRGNvesYP1tb7e4wqdGX3J6je/bpbNRwglnarzIEw37JjCsnhZi9iaUOWbHrvrb98MsLqyugvOtCwt/NGntZ8JJeFHLMHpuHu6uM2H+wotvwE1zSNL4+DScp/vpc4Cc55rksIOaOTB8F2OhxpTnlPzcVs6Av8HYEKyrWl4vSAqS5OcIPkQIDAQAB",
            "tc2ClientId": "9fcfbf759b0b4e5c83cd03cea1d20d59",
        }
    ],
    "brandInfo": [
        {
            "AppID": 16808,
            "BrandName": "totalconnect",
        },
    ],
}

REST_RESULT_TOKEN = {
    "access_token": jwt.encode({"ids": "12345"}, key="key", algorithm="HS256"),
    "refresh_token": "refresh",
    "expires_in": 1200,
}

REST_RESULT_SESSION_DETAILS = {
    "SessionDetailsResult": {
        "ModuleFlags": "Security=1,Video=1,Automation=1,GPS=1,VideoPIR=1,ReadState=1,IsAlexaEnabled=0,SPAEnabled=0,ShowPrivacyLink=0",
        "SessionID": "70F12813-0ABC-4634-AAE0-E56B342E6A21",
        "PrivacyStatementUrl": "https://www.resideo.com/us/en/corporate/legal/eula/english-us/#_PRIVACY_RESIDEO",
        "UserInfo": {
            "UserID": USER_ID,
            "Username": "test_user",
            "Fullname": "Test User",
            "Language": 0,
            "LocaleID": 0,
            "UserFeatureList": "Master=0,User Administration=0,Configuration Administration=0",
            "ClientPreferences": "",
            "IsEulaAccepted": True,
            "IsSMSEulaAccepted": False,
            "DateFormatID": 0,
            "TimeFormatID": 0,
            "PushNotificationStatus": 0,
            "HasResetPassword": True,
            "IsRootedDeviceAccepted": False,
            "IsLocalyticsEnabled": -1,
            "IsAppStoreLogEnabled": -1,
            "IsMarketingOptionEnabled": 1,
            "IsMarketingDefaultValue": 1,
            "IsMonitoringDefaultValue": -1,
            "IsOtpSupported": 1,
            "IsOtpEnabled": 0,
            "UserOtpEmail": None,
            "ForceResetPassword": False,
            "UserCodeDirectPushEnabled": False,
        },
        "Locations": [
            {
                "LocationID": LOCATION_ID,
                "LocationName": LOCATION_NAME,
                "PhotoURL": "",
                "LocationModuleFlags": "Security=1,Video=0,Automation=0,GPS=0,VideoPIR=0,TimeTriggeredEvent=0,TemperatureUnits=F,ConfigureContent=1,SyncLocation=0,ConfigureSlideshow=0,TimezoneOffset=-8.0,SmartAction=1,CustomArm=0,NoTriggerScene=1,NoScene=1,AutoSyncEnabled=1,WiFIThermostatEnabled=1,SupportsOnlyHDPhotos=1,SyncStatusSupported=1,WiFiHBSupported=1,DoorBellSupported=1,masterUserCodeSync=0,GeofenceStatus=0,RSISupported=0,VideoServiceEnabled=0,HasAddressUpdated=1,WifiGaragedoorSupported=0,OutboundServiceEnabled=0,HasSmartScenes=0,MotionViewerServiceEnabled=0,VavEnabled=0,UserManagementDisabled=0,HomeCardUpdatedTimestamp=1/1/1900 12:00:00 AM,CameraPartitionFTUE=True,PostalCodeType=NA,IsGoogleHomeSupported=True,SmsCarrierEnabled=True,IsEMEALocation=0,EdimaxServiceDisabled=True,UnicornSupported=0,IsManageDevicesSupported=True,IsAlexaSupported=False,MonitoringType=-1,SmartActionConfigEnabled=0",
                "SecurityDeviceID": SECURITY_DEVICE_ID,
                "LocationInfoSimple": {
                    "LocationId": LOCATION_ID,
                    "LocationName": LOCATION_NAME,
                    "AccountId": 12345678901,
                    "PhotoId": -1,
                    "TimeZoneId": 7,
                    "PhotoURL": "",
                    "SetDefaultLocationName": False,
                    "SecuritySystemAlias": "",
                    "SecuritySystemPanelDeviceID": SECURITY_DEVICE_ID,
                    "CountryID": 1,
                    "StreetNumber": "",
                    "StreetName": "123 Main Street",
                    "City": "Some Town",
                    "StateID": 5,
                    "PostalCode": "99999",
                    "TemperatureUnits": "F",
                    "Latitude": None,
                    "Longitude": None,
                },
                "PanelConnectionStatusInfo": [
                    {
                        "LocationID": LOCATION_ID,
                        "LocationName": LOCATION_NAME,
                        "PhotoURL": "",
                        "ConnectionStatus": 1,
                        "SyncStatus": 1,
                        "SyncStatusMessage": "",
                        "ConnectionType": 0,
                        "SingnalStrength": None,
                    }
                ],
                "DeviceList": [
                    {
                        "DeviceID": SECURITY_DEVICE_ID,
                        "DeviceName": "test",
                        "DeviceClassID": 1,
                        "DeviceSerialNumber": "1234567890AB",
                        "DeviceFlags": "PromptForUserCode=0,PromptForInstallerCode=0,PromptForImportSecuritySettings=0,AllowUserSlotEditing=0,CalCapable=1,CanBeSentToPanel=1,CanArmNightStay=0,CanSupportMultiPartition=0,PartitionCount=0,MaxPartitionCount=4,OnBoardingSupport=0,PartitionAdded=0,DuplicateUserSyncStatus=0,PanelType=12,PanelVariant=1,BLEDisarmCapable=0,ArmHomeSupported=1,DuplicateUserCodeCheck=1,CanSupportRapid=0,IsKeypadSupported=0,WifiEnrollmentSupported=1,IsConnectedPanel=1,ArmNightInSceneSupported=1,BuiltInCameraSettingsSupported=0,ZWaveThermostatScheduleDisabled=0,MultipleAuthorityLevelSupported=1,VideoOnPanelSupported=1,EnableBLEMode=0,IsPanelWiFiResetSupported=0,IsCompetitorClearBypass=0,IsNotReadyStateSupported=0,isArmStatusWithoutExitDelayNotSupported=0,UserCodeLength=4,UserCodeLengthChanged=0,DoubleDisarmRequired=0,TMSCloudSupported=0,IsAVCEnabled=0",
                        "SecurityPanelTypeID": 12,
                        "DeviceSerialText": None,
                        "DeviceType": None,
                        "DeviceVariants": None,
                        "RestrictedPanel": 0,
                    },
                    {
                        "DeviceID": 6123456,
                        "DeviceName": "Built-In Camera",
                        "DeviceClassID": 6,
                        "DeviceSerialNumber": "2345678901AB",
                        "DeviceFlags": "",
                        "SecurityPanelTypeID": 0,
                        "DeviceSerialText": None,
                        "DeviceType": None,
                        "DeviceVariants": None,
                        "RestrictedPanel": 0,
                    },
                    {
                        "DeviceID": 7123456,
                        "DeviceName": "Front Door",
                        "DeviceClassID": 7,
                        "DeviceSerialNumber": "001234567890",
                        "DeviceFlags": "",
                        "SecurityPanelTypeID": 0,
                        "DeviceSerialText": None,
                        "DeviceType": None,
                        "DeviceVariants": None,
                        "RestrictedPanel": 0,
                    },
                ],
            }
        ],
    },
    "ResultCode": 0,
    "ResultData": "Success",
}

REST_RESULT_PARTITIONS_CONFIG = {
    "Partitions": [
        {
            "PartitionName": "Test1",
            "IsStayArmed": False,
            "IsFireEnabled": False,
            "IsCommonEnabled": False,
            "IsLocked": False,
            "IsNewPartition": False,
            "IsNightStayEnabled": 0,
            "ExitDelayTimer": 0,
            "PartitionID": 1,
            "PartitionArmingState": ArmingState.DISARMED.value,
            "ArmingState": ArmingState.DISARMED.value,
            "OverrideArmingState": 0,
            "OverrideTimeStamp": None,
            "IsAlarmResponded": False,
            "AlarmTriggerTime": None,
            "AlarmTriggerTimeLocalized": None,
        },
        {
            "PartitionName": "Test2",
            "IsStayArmed": False,
            "IsFireEnabled": False,
            "IsCommonEnabled": False,
            "IsLocked": False,
            "IsNewPartition": False,
            "IsNightStayEnabled": 0,
            "ExitDelayTimer": 0,
            "PartitionID": 2,
            "PartitionArmingState": ArmingState.DISARMED.value,
            "ArmingState": ArmingState.DISARMED.value,
            "OverrideArmingState": 0,
            "OverrideTimeStamp": None,
            "IsAlarmResponded": False,
            "AlarmTriggerTime": None,
            "AlarmTriggerTimeLocalized": None,
        },
    ]
}

REST_RESULT_PARTITIONS_ZONES = {
    "ZoneStatus": {
        "Zones": [
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "020000",
                    "LoopNumber": 1,
                    "ResponseType": "1",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 2,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 1,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "030000",
                    "LoopNumber": 1,
                    "ResponseType": "4",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 2,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 3,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "040000",
                    "LoopNumber": 1,
                    "ResponseType": "4",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 2,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 4,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 14,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "050000",
                    "LoopNumber": 1,
                    "ResponseType": "4",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 2,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 5,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 99,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "060000",
                    "LoopNumber": 1,
                    "ResponseType": "1",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 1,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 6,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 12,
            },
            {
                "PartitionId": 1,
                "Batterylevel": 5,
                "Signalstrength": 2,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "070000000000000A",
                    "LoopNumber": 2,
                    "ResponseType": "53",
                    "AlarmReportState": 0,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 15,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 7,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 53,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "080000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 8,
                "ZoneStatus": 1,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "090000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 9,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "100000",
                    "LoopNumber": 1,
                    "ResponseType": "1",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 10,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 1,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "120000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 12,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "130000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 13,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "140000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 1,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 14,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "150000",
                    "LoopNumber": 1,
                    "ResponseType": "3",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 1,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 15,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 3,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "160000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 16,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "170000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 17,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "180000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 18,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "190000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 19,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "200000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 20,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "210000",
                    "LoopNumber": 1,
                    "ResponseType": "14",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 6,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 21,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 14,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "220000",
                    "LoopNumber": 1,
                    "ResponseType": "14",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 6,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 22,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 14,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "230000",
                    "LoopNumber": 1,
                    "ResponseType": "14",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 6,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 23,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 14,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "240000",
                    "LoopNumber": 1,
                    "ResponseType": "9",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 4,
                },
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 24,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": 5,
                "Signalstrength": 3,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "250000000000000A",
                    "LoopNumber": 1,
                    "ResponseType": "23",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 0,
                    "DeviceType": 15,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 25,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 23,
            },
            {
                "PartitionId": 1,
                "Batterylevel": 5,
                "Signalstrength": 5,
                "zoneAdditionalInfo": {
                    "SensorSerialNumber": "260000000000000A",
                    "LoopNumber": 1,
                    "ResponseType": "1",
                    "AlarmReportState": 1,
                    "ZoneSupervisionType": 0,
                    "ChimeState": 1,
                    "DeviceType": 0,
                },
                "CanBeBypassed": 1,
                "ZoneFlags": None,
                "ZoneID": 26,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 1,
                "ZoneTypeId": 1,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": None,
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 800,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 0,
                "ZoneTypeId": 50,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": None,
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 1995,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 0,
                "ZoneTypeId": 9,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": None,
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 1996,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 0,
                "ZoneTypeId": 15,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": None,
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 1998,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 0,
                "ZoneTypeId": 6,
            },
            {
                "PartitionId": 1,
                "Batterylevel": -1,
                "Signalstrength": -1,
                "zoneAdditionalInfo": None,
                "CanBeBypassed": 0,
                "ZoneFlags": None,
                "ZoneID": 1999,
                "ZoneStatus": 0,
                "IsBypassableZone": 0,
                "IsSensingZone": 0,
                "ZoneTypeId": 7,
            },
        ]
    }
}

REST_RESULT_FULL_STATUS = {
    "PanelStatus": {
        "Zones": [
            {
                "ZoneID": 8,
                "ZoneDescription": "Office Side Door",
                "ZoneStatus": 1,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 0,
            },
            {
                "ZoneID": 2,
                "ZoneDescription": "Security",
                "ZoneStatus": ZoneStatus.FAULT.value,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-12-11T09:00:13",
                "ZoneTypeID": ZoneType.SECURITY.value,
                "DeviceType": 0,
            },
            {
                "ZoneID": 3,
                "ZoneDescription": "Fire",
                "ZoneStatus": ZoneStatus.LOW_BATTERY.value,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-06-02T15:41:05",
                "ZoneTypeID": ZoneType.FIRE_SMOKE.value,
                "DeviceType": 2,
            },
            {
                "ZoneID": 4,
                "ZoneDescription": "Gas",
                "ZoneStatus": ZoneStatus.TAMPER.value,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-12-11T09:00:13",
                "ZoneTypeID": ZoneType.CARBON_MONOXIDE.value,
                "DeviceType": 2,
            },
            {
                "ZoneID": 5,
                "ZoneDescription": "Unknown",
                "ZoneStatus": ZoneStatus.NORMAL.value,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-06-02T15:40:59",
                "ZoneTypeID": 99,
                "DeviceType": 2,
            },
            {
                "ZoneID": 6,
                "ZoneDescription": "Temperature",
                "ZoneStatus": ZoneStatus.NORMAL.value,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": ZoneType.MONITOR.value,
                "DeviceType": 0,
            },
            {
                "ZoneID": 7,
                "ZoneDescription": "Doorbell  Other",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 53,
                "DeviceType": 15,
            },
            {
                "ZoneID": 9,
                "ZoneDescription": "Office Back Door",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 0,
            },
            {
                "ZoneID": 10,
                "ZoneDescription": "Master Bedroom  Door",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-06-02T15:40:57",
                "ZoneTypeID": 1,
                "DeviceType": 0,
            },
            {
                "ZoneID": 12,
                "ZoneDescription": "Dining Room Two Door",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 0,
            },
            {
                "ZoneID": 13,
                "ZoneDescription": "Patio  Door",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 0,
            },
            {
                "ZoneID": 14,
                "ZoneDescription": "Living Room  Window",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 1,
            },
            {
                "ZoneID": 15,
                "ZoneDescription": "Living Room Two Window",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 3,
                "DeviceType": 1,
            },
            {
                "ZoneID": 16,
                "ZoneDescription": "Apartment  SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:42:29",
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 17,
                "ZoneDescription": "Upstairs Hallway SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:53:57",
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 18,
                "ZoneDescription": "Downstairs Hallway SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:47:10",
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 19,
                "ZoneDescription": "Kid Bedroom SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:49:07",
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 20,
                "ZoneDescription": "Guest Bedroom SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:50:20",
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 21,
                "ZoneDescription": "Apartment  CarbonMonoxideDetecto",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:41:18",
                "ZoneTypeID": 14,
                "DeviceType": 6,
            },
            {
                "ZoneID": 22,
                "ZoneDescription": "Downstairs Hallway CarbonMonoxid",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:45:39",
                "ZoneTypeID": 14,
                "DeviceType": 6,
            },
            {
                "ZoneID": 23,
                "ZoneDescription": "Upstairs Hallway CarbonMonoxideD",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-04-28T09:52:37",
                "ZoneTypeID": 14,
                "DeviceType": 6,
            },
            {
                "ZoneID": 24,
                "ZoneDescription": "Master Bedroom  SmokeDetector",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 9,
                "DeviceType": 4,
            },
            {
                "ZoneID": 25,
                "ZoneDescription": "Garage Side  Other",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": "2024-12-15T15:14:39",
                "ZoneTypeID": 23,
                "DeviceType": 15,
            },
            {
                "ZoneID": 26,
                "ZoneDescription": "Front Door  Door",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 1,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 1,
                "DeviceType": 0,
            },
            {
                "ZoneID": 800,
                "ZoneDescription": "Master Bedroom Keypad",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 50,
                "DeviceType": 0,
            },
            {
                "ZoneID": 1995,
                "ZoneDescription": "Zone 995 Fire",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 9,
                "DeviceType": 11,
            },
            {
                "ZoneID": 1996,
                "ZoneDescription": "Zone 996 Medical",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 15,
                "DeviceType": 10,
            },
            {
                "ZoneID": 1998,
                "ZoneDescription": "Zone 998 Other",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 6,
                "DeviceType": 15,
            },
            {
                "ZoneID": 1999,
                "ZoneDescription": "Zone 999 Police",
                "ZoneStatus": 0,
                "PartitionID": 1,
                "CanBeBypassed": 0,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
                "ZoneTypeID": 7,
                "DeviceType": 12,
            },
        ],
        "PromptForImportSecuritySettings": False,
        "IsAlarmResponded": False,
        "IsCoverTampered": False,
        "Bell1SupervisionFailure": False,
        "Bell2SupervisionFailure": False,
        "SyncSecDeviceFlag": False,
        "LastUpdatedTimestampTicks": 638746327230000000,
        "ConfigurationSequenceNumber": 72,
        "IsInACLoss": False,
        "IsInLowBattery": False,
        "IsInRfJam": False,
        "IsInBatteryMissing": False,
        "Partitions": [
            {
                "PartitionName": "Test1",
                "IsStayArmed": False,
                "IsFireEnabled": False,
                "IsCommonEnabled": False,
                "IsLocked": False,
                "IsNewPartition": False,
                "IsNightStayEnabled": 0,
                "ExitDelayTimer": 0,
                "PartitionID": 1,
                "PartitionArmingState": ArmingState.DISARMED.value,
                "ArmingState": ArmingState.DISARMED.value,
                "OverrideArmingState": 0,
                "OverrideTimeStamp": None,
                "IsAlarmResponded": False,
                "AlarmTriggerTime": "2024-12-15T23:15:30",
                "AlarmTriggerTimeLocalized": "2024-12-15T15:15:30",
            },
            {
                "PartitionName": "Test2",
                "IsStayArmed": False,
                "IsFireEnabled": False,
                "IsCommonEnabled": False,
                "IsLocked": False,
                "IsNewPartition": False,
                "IsNightStayEnabled": 0,
                "ExitDelayTimer": 0,
                "PartitionID": 2,
                "PartitionArmingState": ArmingState.DISARMED.value,
                "ArmingState": ArmingState.DISARMED.value,
                "OverrideArmingState": 0,
                "OverrideTimeStamp": None,
                "IsAlarmResponded": False,
                "AlarmTriggerTime": None,
                "AlarmTriggerTimeLocalized": None,
            },
        ],
    },
    "ArmingState": 10214,
    "IsSensorTrippedAlarm": False,
    "IsAlarmResponded": False,
    "IsCoverTampered": False,
    "Bell1SupervisionFailure": False,
    "Bell2SupervisionFailure": False,
}


ENDPOINT_FULL_STATUS = make_http_endpoint(
    f"api/v3/locations/{LOCATION_ID}/partitions/fullStatus"
)


TOTALCONNECT_HTTP_REQUEST = (
    "homeassistant.components.totalconnect.TotalConnectClient.http_request"
)


def panel_with_status(state: ArmingState):
    """Return panel fullStatus result with given arming state. Only changes partition 1."""
    RESULT = copy.deepcopy(REST_RESULT_FULL_STATUS)
    RESULT["ArmingState"] = state.value
    RESULT["PanelStatus"]["Partitions"][0]["PartitionArmingState"] = state.value
    RESULT["PanelStatus"]["Partitions"][0]["ArmingState"] = state.value
    return RESULT


# define various fullStatus results for common tests
PANEL_STATUS_DISARMED = panel_with_status(ArmingState.DISARMED)
PANEL_STATUS_ARMED_AWAY = panel_with_status(ArmingState.ARMED_AWAY)
PANEL_STATUS_ARMED_AWAY_INSTANT = panel_with_status(ArmingState.ARMED_AWAY_INSTANT)
PANEL_STATUS_ARMED_CUSTOM = panel_with_status(ArmingState.ARMED_CUSTOM_BYPASS)
PANEL_STATUS_ARMING = panel_with_status(ArmingState.ARMING)
PANEL_STATUS_DISARMING = panel_with_status(ArmingState.DISARMING)
PANEL_STATUS_UNKNOWN = panel_with_status(ArmingState.UNKNOWN)

# Home Assistant 'Armed Home' equals TotalConnect 'Armed Stay'
PANEL_STATUS_ARMED_HOME = panel_with_status(ArmingState.ARMED_STAY)
PANEL_STATUS_ARMED_HOME_INSTANT = panel_with_status(ArmingState.ARMED_STAY_INSTANT)
PANEL_STATUS_ARMED_HOME_NIGHT = panel_with_status(ArmingState.ARMED_STAY_NIGHT)

# Home Assistant 'Triggered' equals TotalConnect 'Alarming'
PANEL_STATUS_TRIGGERED_POLICE = panel_with_status(ArmingState.ALARMING)
PANEL_STATUS_TRIGGERED_FIRE = panel_with_status(ArmingState.ALARMING_FIRE_SMOKE)
PANEL_STATUS_TRIGGERED_GAS = panel_with_status(ArmingState.ALARMING_CARBON_MONOXIDE)


async def setup_platform(
    hass: HomeAssistant, platform: Any, code_required: bool = False
) -> MockConfigEntry:
    """Set up the TotalConnect platform."""
    # first set up a config entry and add it to hass
    if code_required:
        mock_entry = MockConfigEntry(
            domain=DOMAIN, data=CONFIG_DATA, options=OPTIONS_DATA_CODE_REQUIRED
        )
    else:
        mock_entry = MockConfigEntry(
            domain=DOMAIN, data=CONFIG_DATA, options=OPTIONS_DATA
        )
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.totalconnect.PLATFORMS", [platform]),
        requests_mock.Mocker() as mock_request,
    ):
        # mock initial authentication
        mock_request.get(AUTH_CONFIG_ENDPOINT, json=REST_RESULT_CONFIG)
        mock_request.post(AUTH_TOKEN_ENDPOINT, json=REST_RESULT_TOKEN)

        # mock initial fetching of system information
        mock_request.get(
            HTTP_API_SESSION_DETAILS_ENDPOINT, json=REST_RESULT_SESSION_DETAILS
        )
        mock_request.get(
            make_http_endpoint(
                f"api/v1/locations/{LOCATION_ID}/devices/{SECURITY_DEVICE_ID}/partitions/config"
            ),
            json=REST_RESULT_PARTITIONS_CONFIG,
        )
        mock_request.get(
            make_http_endpoint(f"api/v1/locations/{LOCATION_ID}/partitions/zones/0"),
            json=REST_RESULT_PARTITIONS_ZONES,
        )
        mock_request.get(
            ENDPOINT_FULL_STATUS,
            json=REST_RESULT_FULL_STATUS,
        )

        # now set up the components
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    return mock_entry


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the TotalConnect integration."""
    # first set up a config entry and add it to hass
    mock_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_DATA, options=OPTIONS_DATA)
    mock_entry.add_to_hass(hass)

    with requests_mock.Mocker() as mock_request:
        # mock initial authentication
        mock_request.get(AUTH_CONFIG_ENDPOINT, json=REST_RESULT_CONFIG)
        mock_request.post(AUTH_TOKEN_ENDPOINT, json=REST_RESULT_TOKEN)

        # mock initial fetching of system information
        mock_request.get(
            HTTP_API_SESSION_DETAILS_ENDPOINT, json=REST_RESULT_SESSION_DETAILS
        )
        mock_request.get(
            make_http_endpoint(
                f"api/v1/locations/{LOCATION_ID}/devices/{SECURITY_DEVICE_ID}/partitions/config"
            ),
            json=REST_RESULT_PARTITIONS_CONFIG,
        )
        mock_request.get(
            make_http_endpoint(f"api/v1/locations/{LOCATION_ID}/partitions/zones/0"),
            json=REST_RESULT_PARTITIONS_ZONES,
        )
        mock_request.get(
            make_http_endpoint(f"api/v3/locations/{LOCATION_ID}/partitions/fullStatus"),
            json=REST_RESULT_FULL_STATUS,
        )
        await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
