"""ONVIF event parsers."""
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from .models import Event

PARSERS = Registry()


@PARSERS.register("tns1:VideoSource/MotionAlarm")
# pylint: disable=protected-access
async def async_parse_motion_alarm(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:VideoSource/MotionAlarm
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            f"{source} Motion Alarm",
            "binary_sensor",
            "motion",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooBlurry/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/RecordingService")
# pylint: disable=protected-access
async def async_parse_image_too_blurry(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBlurry/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            f"{source} Image Too Blurry",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooDark/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/RecordingService")
# pylint: disable=protected-access
async def async_parse_image_too_dark(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooDark/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            f"{source} Image Too Dark",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooBright/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/RecordingService")
# pylint: disable=protected-access
async def async_parse_image_too_bright(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBright/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            f"{source} Image Too Bright",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/GlobalSceneChange/AnalyticsService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/ImagingService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/RecordingService")
# pylint: disable=protected-access
async def async_parse_scene_change(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:VideoSource/GlobalSceneChange/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            f"{source} Global Scene Change",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:AudioAnalytics/Audio/DetectedSound")
# pylint: disable=protected-access
async def async_parse_detected_sound(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:AudioAnalytics/Audio/DetectedSound
    """
    try:
        audio_source = ""
        audio_analytics = ""
        rule = ""
        for source in msg.Message._value_1.Source.SimpleItem:
            if source.Name == "AudioSourceConfigurationToken":
                audio_source = source.Value
            if source.Name == "AudioAnalyticsConfigurationToken":
                audio_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{msg.Topic._value_1}_{audio_source}_{audio_analytics}_{rule}",
            f"{rule} Detected Sound",
            "binary_sensor",
            "sound",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/FieldDetector/ObjectsInside")
# pylint: disable=protected-access
async def async_parse_field_detector(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/FieldDetector/ObjectsInside
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        for source in msg.Message._value_1.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = source.Value
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        evt = Event(
            f"{uid}_{msg.Topic._value_1}_{video_source}_{video_analytics}_{rule}",
            f"{rule} Field Detection",
            "binary_sensor",
            "motion",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
        return evt
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/CellMotionDetector/Motion")
# pylint: disable=protected-access
async def async_parse_cell_motion_detector(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/CellMotionDetector/Motion
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        for source in msg.Message._value_1.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = source.Value
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{msg.Topic._value_1}_{video_source}_{video_analytics}_{rule}",
            f"{rule} Cell Motion Detection",
            "binary_sensor",
            "motion",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/TamperDetector/Tamper")
# pylint: disable=protected-access
async def async_parse_tamper_detector(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/TamperDetector/Tamper
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        for source in msg.Message._value_1.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = source.Value
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{msg.Topic._value_1}_{video_source}_{video_analytics}_{rule}",
            f"{rule} Tamper Detection",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/HardwareFailure/StorageFailure")
# pylint: disable=protected-access
async def async_parse_storage_failure(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:Device/HardwareFailure/StorageFailure
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Storage Failure",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/ProcessorUsage")
# pylint: disable=protected-access
async def async_parse_processor_usage(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:Monitoring/ProcessorUsage
    """
    try:
        usage = float(msg.Message._value_1.Data.SimpleItem[0].Value)
        if usage <= 1:
            usage *= 100

        return Event(
            f"{uid}_{msg.Topic._value_1}",
            "Processor Usage",
            "sensor",
            None,
            "percent",
            int(usage),
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReboot")
# pylint: disable=protected-access
async def async_parse_last_reboot(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReboot
    """
    try:
        return Event(
            f"{uid}_{msg.Topic._value_1}",
            "Last Reboot",
            "sensor",
            "timestamp",
            None,
            dt_util.as_local(
                dt_util.parse_datetime(msg.Message._value_1.Data.SimpleItem[0].Value)
            ),
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReset")
# pylint: disable=protected-access
async def async_parse_last_reset(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReset
    """
    try:
        return Event(
            f"{uid}_{msg.Topic._value_1}",
            "Last Reset",
            "sensor",
            "timestamp",
            None,
            dt_util.as_local(
                dt_util.parse_datetime(msg.Message._value_1.Data.SimpleItem[0].Value)
            ),
            entity_enabled=False,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastClockSynchronization")
# pylint: disable=protected-access
async def async_parse_last_clock_sync(uid: str, msg) -> Event:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastClockSynchronization
    """
    try:
        return Event(
            f"{uid}_{msg.Topic._value_1}",
            "Last Clock Synchronization",
            "sensor",
            "timestamp",
            None,
            dt_util.as_local(
                dt_util.parse_datetime(msg.Message._value_1.Data.SimpleItem[0].Value)
            ),
            entity_enabled=False,
        )
    except (AttributeError, KeyError):
        return None
