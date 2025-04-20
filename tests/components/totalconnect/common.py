"""Common methods used across tests for TotalConnect."""

import copy
from typing import Any
from unittest.mock import patch

import jwt
import requests_mock
from total_connect_client import ArmingState, ResultCode, ZoneStatus, ZoneType
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

DEVICE_INFO_BASIC_1 = {
    "DeviceID": "987654",
    "DeviceName": "test",
    "DeviceClassID": 1,
    "DeviceSerialNumber": "987654321ABC",
    "DeviceFlags": "PromptForUserCode=0,PromptForInstallerCode=0,PromptForImportSecuritySettings=0,AllowUserSlotEditing=0,CalCapable=1,CanBeSentToPanel=0,CanArmNightStay=0,CanSupportMultiPartition=0,PartitionCount=0,MaxPartitionCount=0,OnBoardingSupport=0,PartitionAdded=0,DuplicateUserSyncStatus=0,PanelType=8,PanelVariant=1,BLEDisarmCapable=0,ArmHomeSupported=0,DuplicateUserCodeCheck=1,CanSupportRapid=0,IsKeypadSupported=1,WifiEnrollmentSupported=0,IsConnectedPanel=0,ArmNightInSceneSupported=0,BuiltInCameraSettingsSupported=0,ZWaveThermostatScheduleDisabled=0,MultipleAuthorityLevelSupported=0,VideoOnPanelSupported=0,EnableBLEMode=0,IsPanelWiFiResetSupported=0,IsCompetitorClearBypass=0,IsNotReadyStateSupported=0,isArmStatusWithoutExitDelayNotSupported=0",
    "SecurityPanelTypeID": None,
    "DeviceSerialText": None,
}
DEVICE_LIST = [DEVICE_INFO_BASIC_1]

LOCATION_INFO_BASIC_NORMAL = {
    "LocationID": LOCATION_ID,
    "LocationName": "test",
    "SecurityDeviceID": "987654",
    "PhotoURL": "http://www.example.com/some/path/to/file.jpg",
    "LocationModuleFlags": "Security=1,Video=0,Automation=0,GPS=0,VideoPIR=0",
    "DeviceList": {"DeviceInfoBasic": DEVICE_LIST},
}

LOCATIONS = {"LocationInfoBasic": [LOCATION_INFO_BASIC_NORMAL]}

MODULE_FLAGS = "Some=0,Fake=1,Flags=2"

USER = {
    "UserID": "1234567",
    "Username": "username",
    "UserFeatureList": "Master=0,User Administration=0,Configuration Administration=0",
}

RESPONSE_SESSION_DETAILS = {
    "ResultCode": ResultCode.SUCCESS.value,
    "ResultData": "Success",
    "SessionID": "12345",
    "Locations": LOCATIONS,
    "ModuleFlags": MODULE_FLAGS,
    "UserInfo": USER,
}

PARTITION_DISARMED = {
    "PartitionID": "1",
    "ArmingState": ArmingState.DISARMED,
}

PARTITION_DISARMED2 = {
    "PartitionID": "2",
    "ArmingState": ArmingState.DISARMED,
}

PARTITION_ARMED_STAY = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_STAY,
}

PARTITION_ARMED_STAY2 = {
    "PartitionID": "2",
    "ArmingState": ArmingState.DISARMED,
}

PARTITION_ARMED_AWAY = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_AWAY,
}

PARTITION_ARMED_CUSTOM = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_CUSTOM_BYPASS,
}

PARTITION_ARMED_NIGHT = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_STAY_NIGHT,
}

PARTITION_ARMING = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMING,
}
PARTITION_DISARMING = {
    "PartitionID": "1",
    "ArmingState": ArmingState.DISARMING,
}

PARTITION_TRIGGERED_POLICE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING,
}

PARTITION_TRIGGERED_FIRE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING_FIRE_SMOKE,
}

PARTITION_TRIGGERED_CARBON_MONOXIDE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING_CARBON_MONOXIDE,
}

PARTITION_UNKNOWN = {
    "PartitionID": "1",
    "ArmingState": "99999",
}


PARTITION_INFO_DISARMED = [PARTITION_DISARMED, PARTITION_DISARMED2]
PARTITION_INFO_ARMED_STAY = [PARTITION_ARMED_STAY, PARTITION_ARMED_STAY2]
PARTITION_INFO_ARMED_AWAY = [PARTITION_ARMED_AWAY]
PARTITION_INFO_ARMED_CUSTOM = [PARTITION_ARMED_CUSTOM]
PARTITION_INFO_ARMED_NIGHT = [PARTITION_ARMED_NIGHT]
PARTITION_INFO_ARMING = [PARTITION_ARMING]
PARTITION_INFO_DISARMING = [PARTITION_DISARMING]
PARTITION_INFO_TRIGGERED_POLICE = [PARTITION_TRIGGERED_POLICE]
PARTITION_INFO_TRIGGERED_FIRE = [PARTITION_TRIGGERED_FIRE]
PARTITION_INFO_TRIGGERED_CARBON_MONOXIDE = [PARTITION_TRIGGERED_CARBON_MONOXIDE]
PARTITION_INFO_UNKNOWN = [PARTITION_UNKNOWN]

PARTITIONS_DISARMED = {"PartitionInfo": PARTITION_INFO_DISARMED}
PARTITIONS_ARMED_STAY = {"PartitionInfo": PARTITION_INFO_ARMED_STAY}
PARTITIONS_ARMED_AWAY = {"PartitionInfo": PARTITION_INFO_ARMED_AWAY}
PARTITIONS_ARMED_CUSTOM = {"PartitionInfo": PARTITION_INFO_ARMED_CUSTOM}
PARTITIONS_ARMED_NIGHT = {"PartitionInfo": PARTITION_INFO_ARMED_NIGHT}
PARTITIONS_ARMING = {"PartitionInfo": PARTITION_INFO_ARMING}
PARTITIONS_DISARMING = {"PartitionInfo": PARTITION_INFO_DISARMING}
PARTITIONS_TRIGGERED_POLICE = {"PartitionInfo": PARTITION_INFO_TRIGGERED_POLICE}
PARTITIONS_TRIGGERED_FIRE = {"PartitionInfo": PARTITION_INFO_TRIGGERED_FIRE}
PARTITIONS_TRIGGERED_CARBON_MONOXIDE = {
    "PartitionInfo": PARTITION_INFO_TRIGGERED_CARBON_MONOXIDE
}
PARTITIONS_UNKNOWN = {"PartitionInfo": PARTITION_INFO_UNKNOWN}

ZONE_NORMAL = {
    "ZoneID": "1",
    "ZoneDescription": "Security",
    "ZoneStatus": ZoneStatus.FAULT,
    "ZoneTypeId": ZoneType.SECURITY,
    "PartitionId": "1",
    "CanBeBypassed": 1,
}
ZONE_2 = {
    "ZoneID": "2",
    "ZoneDescription": "Fire",
    "ZoneStatus": ZoneStatus.LOW_BATTERY,
    "ZoneTypeId": ZoneType.FIRE_SMOKE,
    "PartitionId": "1",
    "CanBeBypassed": 1,
}
ZONE_3 = {
    "ZoneID": "3",
    "ZoneDescription": "Gas",
    "ZoneStatus": ZoneStatus.TAMPER,
    "ZoneTypeId": ZoneType.CARBON_MONOXIDE,
    "PartitionId": "1",
    "CanBeBypassed": 1,
}
ZONE_4 = {
    "ZoneID": "4",
    "ZoneDescription": "Motion",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": ZoneType.INTERIOR_FOLLOWER,
    "PartitionId": "1",
    "CanBeBypassed": 1,
}
ZONE_5 = {
    "ZoneID": "5",
    "ZoneDescription": "Medical",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": ZoneType.PROA7_MEDICAL,
    "PartitionId": "1",
    "CanBeBypassed": 0,
}
# 99 is an unknown ZoneType
ZONE_6 = {
    "ZoneID": "6",
    "ZoneDescription": "Unknown",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": 99,
    "PartitionId": "1",
    "CanBeBypassed": 0,
}

ZONE_7 = {
    "ZoneID": 7,
    "ZoneDescription": "Temperature",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": ZoneType.MONITOR,
    "PartitionId": "1",
    "CanBeBypassed": 0,
}

# ZoneType security that cannot be bypassed is a Button on the alarm panel
ZONE_8 = {
    "ZoneID": 8,
    "ZoneDescription": "Button",
    "ZoneStatus": ZoneStatus.FAULT,
    "ZoneTypeId": ZoneType.SECURITY,
    "PartitionId": "1",
    "CanBeBypassed": 0,
}


ZONE_INFO = [ZONE_NORMAL, ZONE_2, ZONE_3, ZONE_4, ZONE_5, ZONE_6, ZONE_7]
ZONES = {"ZoneInfo": ZONE_INFO}

METADATA_DISARMED = {
    "Partitions": PARTITIONS_DISARMED,
    "Zones": ZONES,
    "PromptForImportSecuritySettings": False,
    "IsInACLoss": False,
    "IsCoverTampered": False,
    "Bell1SupervisionFailure": False,
    "Bell2SupervisionFailure": False,
    "IsInLowBattery": False,
}

METADATA_ARMED_STAY = METADATA_DISARMED.copy()
METADATA_ARMED_STAY["Partitions"] = PARTITIONS_ARMED_STAY

METADATA_ARMED_AWAY = METADATA_DISARMED.copy()
METADATA_ARMED_AWAY["Partitions"] = PARTITIONS_ARMED_AWAY

METADATA_ARMED_CUSTOM = METADATA_DISARMED.copy()
METADATA_ARMED_CUSTOM["Partitions"] = PARTITIONS_ARMED_CUSTOM

METADATA_ARMED_NIGHT = METADATA_DISARMED.copy()
METADATA_ARMED_NIGHT["Partitions"] = PARTITIONS_ARMED_NIGHT

METADATA_ARMING = METADATA_DISARMED.copy()
METADATA_ARMING["Partitions"] = PARTITIONS_ARMING

METADATA_DISARMING = METADATA_DISARMED.copy()
METADATA_DISARMING["Partitions"] = PARTITIONS_DISARMING

METADATA_TRIGGERED_POLICE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_POLICE["Partitions"] = PARTITIONS_TRIGGERED_POLICE

METADATA_TRIGGERED_FIRE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_FIRE["Partitions"] = PARTITIONS_TRIGGERED_FIRE

METADATA_TRIGGERED_CARBON_MONOXIDE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_CARBON_MONOXIDE["Partitions"] = PARTITIONS_TRIGGERED_CARBON_MONOXIDE

METADATA_UNKNOWN = METADATA_DISARMED.copy()
METADATA_UNKNOWN["Partitions"] = PARTITIONS_UNKNOWN

RESPONSE_DISARMED = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_DISARMED,
    "ArmingState": ArmingState.DISARMED,
}
RESPONSE_ARMED_STAY = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_STAY,
    "ArmingState": ArmingState.ARMED_STAY,
}
RESPONSE_ARMED_AWAY = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_AWAY,
    "ArmingState": ArmingState.ARMED_AWAY,
}
RESPONSE_ARMED_CUSTOM = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_CUSTOM,
    "ArmingState": ArmingState.ARMED_CUSTOM_BYPASS,
}
RESPONSE_ARMED_NIGHT = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_NIGHT,
    "ArmingState": ArmingState.ARMED_STAY_NIGHT,
}
RESPONSE_ARMING = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMING,
    "ArmingState": ArmingState.ARMING,
}
RESPONSE_DISARMING = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_DISARMING,
    "ArmingState": ArmingState.DISARMING,
}
RESPONSE_TRIGGERED_POLICE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_POLICE,
    "ArmingState": ArmingState.ALARMING,
}
RESPONSE_TRIGGERED_FIRE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_FIRE,
    "ArmingState": ArmingState.ALARMING_FIRE_SMOKE,
}
RESPONSE_TRIGGERED_CARBON_MONOXIDE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_CARBON_MONOXIDE,
    "ArmingState": ArmingState.ALARMING_CARBON_MONOXIDE,
}
RESPONSE_UNKNOWN = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_UNKNOWN,
    "ArmingState": ArmingState.DISARMED,
}

RESPONSE_ARM_SUCCESS = {"ResultCode": ResultCode.ARM_SUCCESS.value}
RESPONSE_ARM_FAILURE = {"ResultCode": ResultCode.COMMAND_FAILED.value}
RESPONSE_DISARM_SUCCESS = {"ResultCode": ResultCode.DISARM_SUCCESS.value}
RESPONSE_DISARM_FAILURE = {
    "ResultCode": ResultCode.COMMAND_FAILED.value,
    "ResultData": "Command Failed",
}
RESPONSE_USER_CODE_INVALID = {
    "ResultCode": ResultCode.USER_CODE_INVALID.value,
    "ResultData": "testing user code invalid",
}
RESPONSE_SUCCESS = {"ResultCode": ResultCode.SUCCESS.value}
RESPONSE_ZONE_BYPASS_SUCCESS = {
    "ResultCode": ResultCode.SUCCESS.value,
    "ResultData": "None",
}
RESPONSE_ZONE_BYPASS_FAILURE = {
    "ResultCode": ResultCode.FAILED_TO_BYPASS_ZONE.value,
    "ResultData": "None",
}

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

PARTITION_DETAILS_1 = {
    "PartitionID": "1",
    "ArmingState": ArmingState.DISARMED.value,
    "PartitionName": "Test1",
}

PARTITION_DETAILS_2 = {
    "PartitionID": "2",
    "ArmingState": ArmingState.DISARMED.value,
    "PartitionName": "Test2",
}

PARTITION_DETAILS = {"PartitionDetails": [PARTITION_DETAILS_1, PARTITION_DETAILS_2]}
RESPONSE_PARTITION_DETAILS = {
    "ResultCode": ResultCode.SUCCESS.value,
    "ResultData": "testing partition details",
    "PartitionsInfoList": PARTITION_DETAILS,
}

ZONE_DETAILS_NORMAL = {
    "PartitionId": "1",
    "Batterylevel": "-1",
    "Signalstrength": "-1",
    "zoneAdditionalInfo": None,
    "ZoneID": "1",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": ZoneType.SECURITY,
    "CanBeBypassed": 1,
    "ZoneFlags": None,
}

ZONE_STATUS_INFO = [ZONE_DETAILS_NORMAL]
ZONE_DETAILS = {"ZoneStatusInfoWithPartitionId": ZONE_STATUS_INFO}
ZONE_DETAIL_STATUS = {"Zones": ZONE_DETAILS}

RESPONSE_GET_ZONE_DETAILS_SUCCESS = {
    "ResultCode": 0,
    "ResultData": "Success",
    "ZoneStatus": ZONE_DETAIL_STATUS,
}

TOTALCONNECT_REQUEST = (
    "homeassistant.components.totalconnect.TotalConnectClient.request"
)
TOTALCONNECT_GET_CONFIG = (
    "homeassistant.components.totalconnect.TotalConnectClient._get_configuration"
)
TOTALCONNECT_REQUEST_TOKEN = (
    "homeassistant.components.totalconnect.TotalConnectClient._request_token"
)


################################################ NEW TEST DATA ##########################################

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
