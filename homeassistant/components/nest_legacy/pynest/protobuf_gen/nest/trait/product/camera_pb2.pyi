import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CameraState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CAMERA_UNSPECIFIED: _ClassVar[CameraState]
    CAMERA_ON: _ClassVar[CameraState]
    CAMERA_OFF: _ClassVar[CameraState]

class VideoHistorySetting(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VIDEO_HISTORY_UNSPECIFIED: _ClassVar[VideoHistorySetting]
    VIDEO_HISTORY_LEGACY_NONE: _ClassVar[VideoHistorySetting]
    VIDEO_HISTORY_EVENTS_24_7: _ClassVar[VideoHistorySetting]
    VIDEO_HISTORY_EVENTS: _ClassVar[VideoHistorySetting]
    VIDEO_HISTORY_LEGACY_EVENTS: _ClassVar[VideoHistorySetting]
    VIDEO_HISTORY_NONE: _ClassVar[VideoHistorySetting]
CAMERA_UNSPECIFIED: CameraState
CAMERA_ON: CameraState
CAMERA_OFF: CameraState
VIDEO_HISTORY_UNSPECIFIED: VideoHistorySetting
VIDEO_HISTORY_LEGACY_NONE: VideoHistorySetting
VIDEO_HISTORY_EVENTS_24_7: VideoHistorySetting
VIDEO_HISTORY_EVENTS: VideoHistorySetting
VIDEO_HISTORY_LEGACY_EVENTS: VideoHistorySetting
VIDEO_HISTORY_NONE: VideoHistorySetting

class RecordingToggleSettingsTrait(_message.Message):
    __slots__ = ("targetCameraState", "changeModeReason", "settingsUpdated")
    TARGETCAMERASTATE_FIELD_NUMBER: _ClassVar[int]
    CHANGEMODEREASON_FIELD_NUMBER: _ClassVar[int]
    SETTINGSUPDATED_FIELD_NUMBER: _ClassVar[int]
    targetCameraState: CameraState
    changeModeReason: int
    settingsUpdated: _timestamp_pb2.Timestamp
    def __init__(self, targetCameraState: _Optional[_Union[CameraState, str]] = ..., changeModeReason: _Optional[int] = ..., settingsUpdated: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RecordingToggleTrait(_message.Message):
    __slots__ = ("currentCameraState", "changeModeReason", "toggleUpdated")
    CURRENTCAMERASTATE_FIELD_NUMBER: _ClassVar[int]
    CHANGEMODEREASON_FIELD_NUMBER: _ClassVar[int]
    TOGGLEUPDATED_FIELD_NUMBER: _ClassVar[int]
    currentCameraState: CameraState
    changeModeReason: int
    toggleUpdated: _timestamp_pb2.Timestamp
    def __init__(self, currentCameraState: _Optional[_Union[CameraState, str]] = ..., changeModeReason: _Optional[int] = ..., toggleUpdated: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RecordingEncoderSettingsTrait(_message.Message):
    __slots__ = ("recordingQuality",)
    class RecordingQuality(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RECORDING_QUALITY_UNSPECIFIED: _ClassVar[RecordingEncoderSettingsTrait.RecordingQuality]
        RECORDING_QUALITY_LOW: _ClassVar[RecordingEncoderSettingsTrait.RecordingQuality]
        RECORDING_QUALITY_MEDIUM: _ClassVar[RecordingEncoderSettingsTrait.RecordingQuality]
        RECORDING_QUALITY_MEDIUM_HIGH: _ClassVar[RecordingEncoderSettingsTrait.RecordingQuality]
        RECORDING_QUALITY_HIGH: _ClassVar[RecordingEncoderSettingsTrait.RecordingQuality]
    RECORDING_QUALITY_UNSPECIFIED: RecordingEncoderSettingsTrait.RecordingQuality
    RECORDING_QUALITY_LOW: RecordingEncoderSettingsTrait.RecordingQuality
    RECORDING_QUALITY_MEDIUM: RecordingEncoderSettingsTrait.RecordingQuality
    RECORDING_QUALITY_MEDIUM_HIGH: RecordingEncoderSettingsTrait.RecordingQuality
    RECORDING_QUALITY_HIGH: RecordingEncoderSettingsTrait.RecordingQuality
    RECORDINGQUALITY_FIELD_NUMBER: _ClassVar[int]
    recordingQuality: RecordingEncoderSettingsTrait.RecordingQuality
    def __init__(self, recordingQuality: _Optional[_Union[RecordingEncoderSettingsTrait.RecordingQuality, str]] = ...) -> None: ...

class MediaQualitySettingsTrait(_message.Message):
    __slots__ = ("mediaQuality",)
    class MediaQuality(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MEDIA_QUALITY_UNSPECIFIED: _ClassVar[MediaQualitySettingsTrait.MediaQuality]
        MEDIA_QUALITY_LOW_OR_MEDIUM: _ClassVar[MediaQualitySettingsTrait.MediaQuality]
        MEDIA_QUALITY_HIGH: _ClassVar[MediaQualitySettingsTrait.MediaQuality]
    MEDIA_QUALITY_UNSPECIFIED: MediaQualitySettingsTrait.MediaQuality
    MEDIA_QUALITY_LOW_OR_MEDIUM: MediaQualitySettingsTrait.MediaQuality
    MEDIA_QUALITY_HIGH: MediaQualitySettingsTrait.MediaQuality
    MEDIAQUALITY_FIELD_NUMBER: _ClassVar[int]
    mediaQuality: MediaQualitySettingsTrait.MediaQuality
    def __init__(self, mediaQuality: _Optional[_Union[MediaQualitySettingsTrait.MediaQuality, str]] = ...) -> None: ...

class ActivityZoneSettingsTrait(_message.Message):
    __slots__ = ("activityZones", "unknown")
    class ActivityZone(_message.Message):
        __slots__ = ("zoneIndex", "zoneProperties")
        class ActivityZoneProperties(_message.Message):
            __slots__ = ("name", "internalIndex", "vertices", "zoneId")
            class Coordinate(_message.Message):
                __slots__ = ("x", "y")
                X_FIELD_NUMBER: _ClassVar[int]
                Y_FIELD_NUMBER: _ClassVar[int]
                x: float
                y: float
                def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...
            NAME_FIELD_NUMBER: _ClassVar[int]
            INTERNALINDEX_FIELD_NUMBER: _ClassVar[int]
            VERTICES_FIELD_NUMBER: _ClassVar[int]
            ZONEID_FIELD_NUMBER: _ClassVar[int]
            name: str
            internalIndex: int
            vertices: _containers.RepeatedCompositeFieldContainer[ActivityZoneSettingsTrait.ActivityZone.ActivityZoneProperties.Coordinate]
            zoneId: int
            def __init__(self, name: _Optional[str] = ..., internalIndex: _Optional[int] = ..., vertices: _Optional[_Iterable[_Union[ActivityZoneSettingsTrait.ActivityZone.ActivityZoneProperties.Coordinate, _Mapping]]] = ..., zoneId: _Optional[int] = ...) -> None: ...
        ZONEINDEX_FIELD_NUMBER: _ClassVar[int]
        ZONEPROPERTIES_FIELD_NUMBER: _ClassVar[int]
        zoneIndex: int
        zoneProperties: ActivityZoneSettingsTrait.ActivityZone.ActivityZoneProperties
        def __init__(self, zoneIndex: _Optional[int] = ..., zoneProperties: _Optional[_Union[ActivityZoneSettingsTrait.ActivityZone.ActivityZoneProperties, _Mapping]] = ...) -> None: ...
    ACTIVITYZONES_FIELD_NUMBER: _ClassVar[int]
    UNKNOWN_FIELD_NUMBER: _ClassVar[int]
    activityZones: _containers.RepeatedCompositeFieldContainer[ActivityZoneSettingsTrait.ActivityZone]
    unknown: int
    def __init__(self, activityZones: _Optional[_Iterable[_Union[ActivityZoneSettingsTrait.ActivityZone, _Mapping]]] = ..., unknown: _Optional[int] = ...) -> None: ...

class FaceTrackingSettingsTrait(_message.Message):
    __slots__ = ("faceTrackingEnabled", "unknown")
    FACETRACKINGENABLED_FIELD_NUMBER: _ClassVar[int]
    UNKNOWN_FIELD_NUMBER: _ClassVar[int]
    faceTrackingEnabled: _wrappers_pb2.BoolValue
    unknown: int
    def __init__(self, faceTrackingEnabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown: _Optional[int] = ...) -> None: ...

class StreamingProtocolTrait(_message.Message):
    __slots__ = ("supportedProtocols", "audioCommunicationType", "directHost", "dashUrl", "hlsUrl")
    class StreamingProtocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PROTOCOL_UNSPECIFIED: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
        PROTOCOL_WEBRTC: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
        PROTOCOL_NEXUSTALK: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
        PROTOCOL_MPEGDASH: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
        PROTOCOL_RTSP: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
        PROTOCOL_HLS: _ClassVar[StreamingProtocolTrait.StreamingProtocol]
    PROTOCOL_UNSPECIFIED: StreamingProtocolTrait.StreamingProtocol
    PROTOCOL_WEBRTC: StreamingProtocolTrait.StreamingProtocol
    PROTOCOL_NEXUSTALK: StreamingProtocolTrait.StreamingProtocol
    PROTOCOL_MPEGDASH: StreamingProtocolTrait.StreamingProtocol
    PROTOCOL_RTSP: StreamingProtocolTrait.StreamingProtocol
    PROTOCOL_HLS: StreamingProtocolTrait.StreamingProtocol
    class AudioCommunicationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUDIO_TYPE_UNSPECIFIED: _ClassVar[StreamingProtocolTrait.AudioCommunicationType]
        AUDIO_TYPE_NONE: _ClassVar[StreamingProtocolTrait.AudioCommunicationType]
        AUDIO_TYPE_HALF_DUPLEX: _ClassVar[StreamingProtocolTrait.AudioCommunicationType]
        AUDIO_TYPE_FULL_DUPLEX: _ClassVar[StreamingProtocolTrait.AudioCommunicationType]
    AUDIO_TYPE_UNSPECIFIED: StreamingProtocolTrait.AudioCommunicationType
    AUDIO_TYPE_NONE: StreamingProtocolTrait.AudioCommunicationType
    AUDIO_TYPE_HALF_DUPLEX: StreamingProtocolTrait.AudioCommunicationType
    AUDIO_TYPE_FULL_DUPLEX: StreamingProtocolTrait.AudioCommunicationType
    SUPPORTEDPROTOCOLS_FIELD_NUMBER: _ClassVar[int]
    AUDIOCOMMUNICATIONTYPE_FIELD_NUMBER: _ClassVar[int]
    DIRECTHOST_FIELD_NUMBER: _ClassVar[int]
    DASHURL_FIELD_NUMBER: _ClassVar[int]
    HLSURL_FIELD_NUMBER: _ClassVar[int]
    supportedProtocols: _containers.RepeatedScalarFieldContainer[StreamingProtocolTrait.StreamingProtocol]
    audioCommunicationType: StreamingProtocolTrait.AudioCommunicationType
    directHost: _wrappers_pb2.StringValue
    dashUrl: _wrappers_pb2.StringValue
    hlsUrl: _wrappers_pb2.StringValue
    def __init__(self, supportedProtocols: _Optional[_Iterable[_Union[StreamingProtocolTrait.StreamingProtocol, str]]] = ..., audioCommunicationType: _Optional[_Union[StreamingProtocolTrait.AudioCommunicationType, str]] = ..., directHost: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., dashUrl: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., hlsUrl: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class LoadingImageTrait(_message.Message):
    __slots__ = ("maximumAgeInSeconds", "liveUrl")
    MAXIMUMAGEINSECONDS_FIELD_NUMBER: _ClassVar[int]
    LIVEURL_FIELD_NUMBER: _ClassVar[int]
    maximumAgeInSeconds: _wrappers_pb2.Int32Value
    liveUrl: str
    def __init__(self, maximumAgeInSeconds: _Optional[_Union[_wrappers_pb2.Int32Value, _Mapping]] = ..., liveUrl: _Optional[str] = ...) -> None: ...

class ObservationTriggerCapabilitiesTrait(_message.Message):
    __slots__ = ("videoEventTypes", "audioEventTypes")
    class VideoEventTypes(_message.Message):
        __slots__ = ("motion", "person", "face", "vehicle", "animal", "package", "unknown7", "unknown8", "unknown9", "unknown10")
        MOTION_FIELD_NUMBER: _ClassVar[int]
        PERSON_FIELD_NUMBER: _ClassVar[int]
        FACE_FIELD_NUMBER: _ClassVar[int]
        VEHICLE_FIELD_NUMBER: _ClassVar[int]
        ANIMAL_FIELD_NUMBER: _ClassVar[int]
        PACKAGE_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN7_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN8_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN9_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN10_FIELD_NUMBER: _ClassVar[int]
        motion: _wrappers_pb2.BoolValue
        person: _wrappers_pb2.BoolValue
        face: _wrappers_pb2.BoolValue
        vehicle: _wrappers_pb2.BoolValue
        animal: _wrappers_pb2.BoolValue
        package: _wrappers_pb2.BoolValue
        unknown7: _wrappers_pb2.BoolValue
        unknown8: _wrappers_pb2.BoolValue
        unknown9: _wrappers_pb2.BoolValue
        unknown10: _wrappers_pb2.BoolValue
        def __init__(self, motion: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., person: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., face: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., vehicle: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., animal: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., package: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown7: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown8: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown9: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown10: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
    class AudioEventTypes(_message.Message):
        __slots__ = ("personTalking", "dogBarking", "unknown3", "unknown4", "otherSounds", "smokeAndCoSounds", "unknown7", "unknown8", "unknown9", "unknown10")
        PERSONTALKING_FIELD_NUMBER: _ClassVar[int]
        DOGBARKING_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN3_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN4_FIELD_NUMBER: _ClassVar[int]
        OTHERSOUNDS_FIELD_NUMBER: _ClassVar[int]
        SMOKEANDCOSOUNDS_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN7_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN8_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN9_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN10_FIELD_NUMBER: _ClassVar[int]
        personTalking: _wrappers_pb2.BoolValue
        dogBarking: _wrappers_pb2.BoolValue
        unknown3: _wrappers_pb2.BoolValue
        unknown4: _wrappers_pb2.BoolValue
        otherSounds: _wrappers_pb2.BoolValue
        smokeAndCoSounds: _wrappers_pb2.BoolValue
        unknown7: _wrappers_pb2.BoolValue
        unknown8: _wrappers_pb2.BoolValue
        unknown9: _wrappers_pb2.BoolValue
        unknown10: _wrappers_pb2.BoolValue
        def __init__(self, personTalking: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., dogBarking: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown3: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown4: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., otherSounds: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., smokeAndCoSounds: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown7: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown8: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown9: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., unknown10: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
    VIDEOEVENTTYPES_FIELD_NUMBER: _ClassVar[int]
    AUDIOEVENTTYPES_FIELD_NUMBER: _ClassVar[int]
    videoEventTypes: ObservationTriggerCapabilitiesTrait.VideoEventTypes
    audioEventTypes: ObservationTriggerCapabilitiesTrait.AudioEventTypes
    def __init__(self, videoEventTypes: _Optional[_Union[ObservationTriggerCapabilitiesTrait.VideoEventTypes, _Mapping]] = ..., audioEventTypes: _Optional[_Union[ObservationTriggerCapabilitiesTrait.AudioEventTypes, _Mapping]] = ...) -> None: ...

class MediaRequestTrait(_message.Message):
    __slots__ = ("unknown1",)
    UNKNOWN1_FIELD_NUMBER: _ClassVar[int]
    unknown1: int
    def __init__(self, unknown1: _Optional[int] = ...) -> None: ...

class UploadLiveImageTrait(_message.Message):
    __slots__ = ("liveImageUrl", "timestamp")
    class UploadLiveImageRequest(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class UploadLiveImageResponse(_message.Message):
        __slots__ = ("status",)
        class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            STATUS_UNSPECIFIED: _ClassVar[UploadLiveImageTrait.UploadLiveImageResponse.Status]
            STATUS_SUCCESSFUL: _ClassVar[UploadLiveImageTrait.UploadLiveImageResponse.Status]
            STATUS_UNSUCCESSFUL: _ClassVar[UploadLiveImageTrait.UploadLiveImageResponse.Status]
        STATUS_UNSPECIFIED: UploadLiveImageTrait.UploadLiveImageResponse.Status
        STATUS_SUCCESSFUL: UploadLiveImageTrait.UploadLiveImageResponse.Status
        STATUS_UNSUCCESSFUL: UploadLiveImageTrait.UploadLiveImageResponse.Status
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: UploadLiveImageTrait.UploadLiveImageResponse.Status
        def __init__(self, status: _Optional[_Union[UploadLiveImageTrait.UploadLiveImageResponse.Status, str]] = ...) -> None: ...
    LIVEIMAGEURL_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    liveImageUrl: str
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, liveImageUrl: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ObservationTriggerSettingsTrait(_message.Message):
    __slots__ = ("globalTriggerSettings", "zoneTriggerSettings", "globalAITriggerSettings")
    class EventTrigger(_message.Message):
        __slots__ = ("enabled",)
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        enabled: _wrappers_pb2.BoolValue
        def __init__(self, enabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
    class SoundTriggerSettings(_message.Message):
        __slots__ = ("personTalking", "dogBarking", "unknown3", "unknown4", "smokeAlarmSounds", "carbonMonoxideAlarmSounds")
        PERSONTALKING_FIELD_NUMBER: _ClassVar[int]
        DOGBARKING_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN3_FIELD_NUMBER: _ClassVar[int]
        UNKNOWN4_FIELD_NUMBER: _ClassVar[int]
        SMOKEALARMSOUNDS_FIELD_NUMBER: _ClassVar[int]
        CARBONMONOXIDEALARMSOUNDS_FIELD_NUMBER: _ClassVar[int]
        personTalking: ObservationTriggerSettingsTrait.EventTrigger
        dogBarking: ObservationTriggerSettingsTrait.EventTrigger
        unknown3: ObservationTriggerSettingsTrait.EventTrigger
        unknown4: ObservationTriggerSettingsTrait.EventTrigger
        smokeAlarmSounds: ObservationTriggerSettingsTrait.EventTrigger
        carbonMonoxideAlarmSounds: ObservationTriggerSettingsTrait.EventTrigger
        def __init__(self, personTalking: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., dogBarking: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., unknown3: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., unknown4: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., smokeAlarmSounds: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., carbonMonoxideAlarmSounds: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ...) -> None: ...
    class ZoneTriggerSettings(_message.Message):
        __slots__ = ("zoneIndex", "zoneSettings")
        class ZoneSettings(_message.Message):
            __slots__ = ("zoneId", "triggerTypes")
            class TriggerTypes(_message.Message):
                __slots__ = ("motion", "person", "face", "vehicle", "animal", "package")
                MOTION_FIELD_NUMBER: _ClassVar[int]
                PERSON_FIELD_NUMBER: _ClassVar[int]
                FACE_FIELD_NUMBER: _ClassVar[int]
                VEHICLE_FIELD_NUMBER: _ClassVar[int]
                ANIMAL_FIELD_NUMBER: _ClassVar[int]
                PACKAGE_FIELD_NUMBER: _ClassVar[int]
                motion: ObservationTriggerSettingsTrait.EventTrigger
                person: ObservationTriggerSettingsTrait.EventTrigger
                face: ObservationTriggerSettingsTrait.EventTrigger
                vehicle: ObservationTriggerSettingsTrait.EventTrigger
                animal: ObservationTriggerSettingsTrait.EventTrigger
                package: ObservationTriggerSettingsTrait.EventTrigger
                def __init__(self, motion: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., person: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., face: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., vehicle: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., animal: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ..., package: _Optional[_Union[ObservationTriggerSettingsTrait.EventTrigger, _Mapping]] = ...) -> None: ...
            ZONEID_FIELD_NUMBER: _ClassVar[int]
            TRIGGERTYPES_FIELD_NUMBER: _ClassVar[int]
            zoneId: int
            triggerTypes: ObservationTriggerSettingsTrait.ZoneTriggerSettings.ZoneSettings.TriggerTypes
            def __init__(self, zoneId: _Optional[int] = ..., triggerTypes: _Optional[_Union[ObservationTriggerSettingsTrait.ZoneTriggerSettings.ZoneSettings.TriggerTypes, _Mapping]] = ...) -> None: ...
        ZONEINDEX_FIELD_NUMBER: _ClassVar[int]
        ZONESETTINGS_FIELD_NUMBER: _ClassVar[int]
        zoneIndex: int
        zoneSettings: ObservationTriggerSettingsTrait.ZoneTriggerSettings.ZoneSettings
        def __init__(self, zoneIndex: _Optional[int] = ..., zoneSettings: _Optional[_Union[ObservationTriggerSettingsTrait.ZoneTriggerSettings.ZoneSettings, _Mapping]] = ...) -> None: ...
    class AITriggerSettings(_message.Message):
        __slots__ = ("seenSettings",)
        class AISeenSettings(_message.Message):
            __slots__ = ("garageDoor",)
            GARAGEDOOR_FIELD_NUMBER: _ClassVar[int]
            garageDoor: bool
            def __init__(self, garageDoor: bool = ...) -> None: ...
        SEENSETTINGS_FIELD_NUMBER: _ClassVar[int]
        seenSettings: ObservationTriggerSettingsTrait.AITriggerSettings.AISeenSettings
        def __init__(self, seenSettings: _Optional[_Union[ObservationTriggerSettingsTrait.AITriggerSettings.AISeenSettings, _Mapping]] = ...) -> None: ...
    GLOBALTRIGGERSETTINGS_FIELD_NUMBER: _ClassVar[int]
    ZONETRIGGERSETTINGS_FIELD_NUMBER: _ClassVar[int]
    GLOBALAITRIGGERSETTINGS_FIELD_NUMBER: _ClassVar[int]
    globalTriggerSettings: ObservationTriggerSettingsTrait.SoundTriggerSettings
    zoneTriggerSettings: _containers.RepeatedCompositeFieldContainer[ObservationTriggerSettingsTrait.ZoneTriggerSettings]
    globalAITriggerSettings: ObservationTriggerSettingsTrait.AITriggerSettings
    def __init__(self, globalTriggerSettings: _Optional[_Union[ObservationTriggerSettingsTrait.SoundTriggerSettings, _Mapping]] = ..., zoneTriggerSettings: _Optional[_Iterable[_Union[ObservationTriggerSettingsTrait.ZoneTriggerSettings, _Mapping]]] = ..., globalAITriggerSettings: _Optional[_Union[ObservationTriggerSettingsTrait.AITriggerSettings, _Mapping]] = ...) -> None: ...

class RecordingMediaSettingsTrait(_message.Message):
    __slots__ = ("videoHistory", "audioHistoryEnabled", "unknown3")
    VIDEOHISTORY_FIELD_NUMBER: _ClassVar[int]
    AUDIOHISTORYENABLED_FIELD_NUMBER: _ClassVar[int]
    UNKNOWN3_FIELD_NUMBER: _ClassVar[int]
    videoHistory: VideoHistorySetting
    audioHistoryEnabled: bool
    unknown3: int
    def __init__(self, videoHistory: _Optional[_Union[VideoHistorySetting, str]] = ..., audioHistoryEnabled: bool = ..., unknown3: _Optional[int] = ...) -> None: ...

class AspectRatioTrait(_message.Message):
    __slots__ = ("widthRelative", "heightRelative")
    WIDTHRELATIVE_FIELD_NUMBER: _ClassVar[int]
    HEIGHTRELATIVE_FIELD_NUMBER: _ClassVar[int]
    widthRelative: int
    heightRelative: int
    def __init__(self, widthRelative: _Optional[int] = ..., heightRelative: _Optional[int] = ...) -> None: ...

class QuietTimeSettingsTrait(_message.Message):
    __slots__ = ("quietTimeEnds",)
    QUIETTIMEENDS_FIELD_NUMBER: _ClassVar[int]
    quietTimeEnds: _timestamp_pb2.Timestamp
    def __init__(self, quietTimeEnds: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class EventSessionTrait(_message.Message):
    __slots__ = ("eventActive",)
    EVENTACTIVE_FIELD_NUMBER: _ClassVar[int]
    eventActive: bool
    def __init__(self, eventActive: bool = ...) -> None: ...

class RecordingMediaCapabilitiesTrait(_message.Message):
    __slots__ = ("supportedCapabilities",)
    SUPPORTEDCAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    supportedCapabilities: _containers.RepeatedScalarFieldContainer[VideoHistorySetting]
    def __init__(self, supportedCapabilities: _Optional[_Iterable[_Union[VideoHistorySetting, str]]] = ...) -> None: ...

class EffectiveHistoryLengthTrait(_message.Message):
    __slots__ = ("historyDurationSeconds",)
    HISTORYDURATIONSECONDS_FIELD_NUMBER: _ClassVar[int]
    historyDurationSeconds: _wrappers_pb2.UInt32Value
    def __init__(self, historyDurationSeconds: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ...) -> None: ...

class CameraMigrationStatusTrait(_message.Message):
    __slots__ = ("state",)
    class MigrationState(_message.Message):
        __slots__ = ("where", "progress")
        class WhereMigrated(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            NOT_MIGRATED: _ClassVar[CameraMigrationStatusTrait.MigrationState.WhereMigrated]
            MIGRATED_TO_GOOGLE_HOME: _ClassVar[CameraMigrationStatusTrait.MigrationState.WhereMigrated]
            MIGRATED_TO_NEST: _ClassVar[CameraMigrationStatusTrait.MigrationState.WhereMigrated]
        NOT_MIGRATED: CameraMigrationStatusTrait.MigrationState.WhereMigrated
        MIGRATED_TO_GOOGLE_HOME: CameraMigrationStatusTrait.MigrationState.WhereMigrated
        MIGRATED_TO_NEST: CameraMigrationStatusTrait.MigrationState.WhereMigrated
        class MigrationProgress(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            PROGRESS_NONE: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
            PROGRESS_STARTING: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
            PROGRESS_INSTALLING: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
            PROGRESS_COMPLETE: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
            PROGRESS_MAYBE_ERROR: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
            PROGRESS_FINALISING: _ClassVar[CameraMigrationStatusTrait.MigrationState.MigrationProgress]
        PROGRESS_NONE: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        PROGRESS_STARTING: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        PROGRESS_INSTALLING: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        PROGRESS_COMPLETE: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        PROGRESS_MAYBE_ERROR: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        PROGRESS_FINALISING: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        WHERE_FIELD_NUMBER: _ClassVar[int]
        PROGRESS_FIELD_NUMBER: _ClassVar[int]
        where: CameraMigrationStatusTrait.MigrationState.WhereMigrated
        progress: CameraMigrationStatusTrait.MigrationState.MigrationProgress
        def __init__(self, where: _Optional[_Union[CameraMigrationStatusTrait.MigrationState.WhereMigrated, str]] = ..., progress: _Optional[_Union[CameraMigrationStatusTrait.MigrationState.MigrationProgress, str]] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: CameraMigrationStatusTrait.MigrationState
    def __init__(self, state: _Optional[_Union[CameraMigrationStatusTrait.MigrationState, _Mapping]] = ...) -> None: ...

class DoorStateTrait(_message.Message):
    __slots__ = ("state",)
    class DoorState(_message.Message):
        __slots__ = ("openClose",)
        class DoorOpenCloseState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            STATE_UNSPECIFIED: _ClassVar[DoorStateTrait.DoorState.DoorOpenCloseState]
            STATE_MAYBE_CLOSING: _ClassVar[DoorStateTrait.DoorState.DoorOpenCloseState]
            STATE_CLOSED: _ClassVar[DoorStateTrait.DoorState.DoorOpenCloseState]
            STATE_MAYBE_OPENING: _ClassVar[DoorStateTrait.DoorState.DoorOpenCloseState]
            STATE_OPEN: _ClassVar[DoorStateTrait.DoorState.DoorOpenCloseState]
        STATE_UNSPECIFIED: DoorStateTrait.DoorState.DoorOpenCloseState
        STATE_MAYBE_CLOSING: DoorStateTrait.DoorState.DoorOpenCloseState
        STATE_CLOSED: DoorStateTrait.DoorState.DoorOpenCloseState
        STATE_MAYBE_OPENING: DoorStateTrait.DoorState.DoorOpenCloseState
        STATE_OPEN: DoorStateTrait.DoorState.DoorOpenCloseState
        class OpenCloseState(_message.Message):
            __slots__ = ("doorState",)
            DOORSTATE_FIELD_NUMBER: _ClassVar[int]
            doorState: DoorStateTrait.DoorState.DoorOpenCloseState
            def __init__(self, doorState: _Optional[_Union[DoorStateTrait.DoorState.DoorOpenCloseState, str]] = ...) -> None: ...
        OPENCLOSE_FIELD_NUMBER: _ClassVar[int]
        openClose: DoorStateTrait.DoorState.OpenCloseState
        def __init__(self, openClose: _Optional[_Union[DoorStateTrait.DoorState.OpenCloseState, _Mapping]] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: DoorStateTrait.DoorState
    def __init__(self, state: _Optional[_Union[DoorStateTrait.DoorState, _Mapping]] = ...) -> None: ...
