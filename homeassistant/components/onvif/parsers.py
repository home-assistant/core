"""ONVIF event parsers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import datetime
from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from .models import Event

PARSERS: Registry[str, Callable[[str, Any], Coroutine[Any, Any, Event | None]]] = (
    Registry()
)

VIDEO_SOURCE_MAPPING = {
    "vsconf": "VideoSourceToken",
}


def extract_message(msg: Any) -> tuple[str, Any]:
    """Extract the message content and the topic."""
    return msg.Topic._value_1, msg.Message._value_1  # noqa: SLF001


def _normalize_video_source(source: str) -> str:
    """Normalize video source.

    Some cameras do not set the VideoSourceToken correctly so we get duplicate
    sensors, so we need to normalize it to the correct value.
    """
    return VIDEO_SOURCE_MAPPING.get(source, source)


def local_datetime_or_none(value: str) -> datetime.datetime | None:
    """Convert strings to datetimes, if invalid, return None."""
    # To handle cameras that return times like '0000-00-00T00:00:00Z' (e.g. hikvision)
    try:
        ret = dt_util.parse_datetime(value)
    except ValueError:
        return None
    if ret is not None:
        return dt_util.as_local(ret)
    return None


@PARSERS.register("tns1:VideoSource/MotionAlarm")
async def async_parse_motion_alarm(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/MotionAlarm
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Motion Alarm",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooBlurry/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/RecordingService")
async def async_parse_image_too_blurry(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBlurry/*
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Image Too Blurry",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooDark/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/RecordingService")
async def async_parse_image_too_dark(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooDark/*
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Image Too Dark",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooBright/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/RecordingService")
async def async_parse_image_too_bright(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBright/*
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Image Too Bright",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/GlobalSceneChange/AnalyticsService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/ImagingService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/RecordingService")
async def async_parse_scene_change(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/GlobalSceneChange/*
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Global Scene Change",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:AudioAnalytics/Audio/DetectedSound")
async def async_parse_detected_sound(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:AudioAnalytics/Audio/DetectedSound
    """
    try:
        audio_source = ""
        audio_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "AudioSourceConfigurationToken":
                audio_source = source.Value
            if source.Name == "AudioAnalyticsConfigurationToken":
                audio_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{audio_source}_{audio_analytics}_{rule}",
            "Detected Sound",
            "binary_sensor",
            "sound",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/FieldDetector/ObjectsInside")
async def async_parse_field_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/FieldDetector/ObjectsInside
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        evt = Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Field Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None
    return evt


@PARSERS.register("tns1:RuleEngine/CellMotionDetector/Motion")
async def async_parse_cell_motion_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/CellMotionDetector/Motion
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Cell Motion Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MotionRegionDetector/Motion")
async def async_parse_motion_region_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MotionRegionDetector/Motion
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Motion Region Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value in ["1", "true"],
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/TamperDetector/Tamper")
async def async_parse_tamper_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/TamperDetector/Tamper
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Tamper Detection",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/DogCatDetect")
async def async_parse_dog_cat_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/DogCatDetect
    """
    try:
        video_source = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "Source":
                video_source = _normalize_video_source(source.Value)

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Pet Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/VehicleDetect")
async def async_parse_vehicle_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/VehicleDetect
    """
    try:
        video_source = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "Source":
                video_source = _normalize_video_source(source.Value)

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Vehicle Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent")
@PARSERS.register("tns1:RuleEngine/PeopleDetector/People")
async def async_parse_tplink_detector(uid: str, msg) -> Event | None:
    """Handle parsing tplink smart event messages.

    Topic: tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent
    Topic: tns1:RuleEngine/PeopleDetector/People
    """
    video_source = ""
    video_analytics = ""
    rule = ""
    topic = ""
    vehicle = False
    person = False
    enabled = False
    try:
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        for item in payload.Data.SimpleItem:
            if item.Name == "IsVehicle":
                vehicle = True
                enabled = item.Value == "true"
            if item.Name == "IsPeople":
                person = True
                enabled = item.Value == "true"
    except (AttributeError, KeyError):
        return None

    if vehicle:
        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Vehicle Detection",
            "binary_sensor",
            "motion",
            None,
            enabled,
        )
    if person:
        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Person Detection",
            "binary_sensor",
            "motion",
            None,
            enabled,
        )

    return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/PeopleDetect")
async def async_parse_person_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/PeopleDetect
    """
    try:
        video_source = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "Source":
                video_source = _normalize_video_source(source.Value)

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Person Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/FaceDetect")
async def async_parse_face_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/FaceDetect
    """
    try:
        video_source = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "Source":
                video_source = _normalize_video_source(source.Value)

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Face Detection",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/Visitor")
async def async_parse_visitor_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/Visitor
    """
    try:
        video_source = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "Source":
                video_source = _normalize_video_source(source.Value)

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Visitor Detection",
            "binary_sensor",
            "occupancy",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/Trigger/DigitalInput")
async def async_parse_digital_input(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/DigitalInput
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Digital Input",
            "binary_sensor",
            None,
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/Trigger/Relay")
async def async_parse_relay(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/Relay
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Relay Triggered",
            "binary_sensor",
            None,
            None,
            payload.Data.SimpleItem[0].Value == "active",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/HardwareFailure/StorageFailure")
async def async_parse_storage_failure(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/HardwareFailure/StorageFailure
    """
    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Storage Failure",
            "binary_sensor",
            "problem",
            None,
            payload.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/ProcessorUsage")
async def async_parse_processor_usage(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/ProcessorUsage
    """
    try:
        topic, payload = extract_message(msg)
        usage = float(payload.Data.SimpleItem[0].Value)
        if usage <= 1:
            usage *= 100

        return Event(
            f"{uid}_{topic}",
            "Processor Usage",
            "sensor",
            None,
            "percent",
            int(usage),
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReboot")
async def async_parse_last_reboot(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReboot
    """
    try:
        topic, payload = extract_message(msg)
        date_time = local_datetime_or_none(payload.Data.SimpleItem[0].Value)
        return Event(
            f"{uid}_{topic}",
            "Last Reboot",
            "sensor",
            "timestamp",
            None,
            date_time,
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReset")
async def async_parse_last_reset(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReset
    """
    try:
        topic, payload = extract_message(msg)
        date_time = local_datetime_or_none(payload.Data.SimpleItem[0].Value)
        return Event(
            f"{uid}_{topic}",
            "Last Reset",
            "sensor",
            "timestamp",
            None,
            date_time,
            EntityCategory.DIAGNOSTIC,
            entity_enabled=False,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/Backup/Last")
async def async_parse_backup_last(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/Backup/Last
    """

    try:
        topic, payload = extract_message(msg)
        date_time = local_datetime_or_none(payload.Data.SimpleItem[0].Value)
        return Event(
            f"{uid}_{topic}",
            "Last Backup",
            "sensor",
            "timestamp",
            None,
            date_time,
            EntityCategory.DIAGNOSTIC,
            entity_enabled=False,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastClockSynchronization")
async def async_parse_last_clock_sync(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastClockSynchronization
    """
    try:
        topic, payload = extract_message(msg)
        date_time = local_datetime_or_none(payload.Data.SimpleItem[0].Value)
        return Event(
            f"{uid}_{topic}",
            "Last Clock Synchronization",
            "sensor",
            "timestamp",
            None,
            date_time,
            EntityCategory.DIAGNOSTIC,
            entity_enabled=False,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RecordingConfig/JobState")
async def async_parse_jobstate(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RecordingConfig/JobState
    """

    try:
        topic, payload = extract_message(msg)
        source = payload.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{topic}_{source}",
            "Recording Job State",
            "binary_sensor",
            None,
            None,
            payload.Data.SimpleItem[0].Value == "Active",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/LineDetector/Crossed")
async def async_parse_linedetector_crossed(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/LineDetector/Crossed
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = source.Value
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Line Detector Crossed",
            "sensor",
            None,
            None,
            payload.Data.SimpleItem[0].Value,
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/CountAggregation/Counter")
async def async_parse_count_aggregation_counter(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/CountAggregation/Counter
    """
    try:
        video_source = ""
        video_analytics = ""
        rule = ""
        topic, payload = extract_message(msg)
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
            if source.Name == "VideoAnalyticsConfigurationToken":
                video_analytics = source.Value
            if source.Name == "Rule":
                rule = source.Value

        return Event(
            f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            "Count Aggregation Counter",
            "sensor",
            None,
            None,
            payload.Data.SimpleItem[0].Value,
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:UserAlarm/IVA/HumanShapeDetect")
async def async_parse_human_shape_detect(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:UserAlarm/IVA/HumanShapeDetect
    """
    try:
        topic, payload = extract_message(msg)
        video_source = ""
        for source in payload.Source.SimpleItem:
            if source.Name == "VideoSourceConfigurationToken":
                video_source = _normalize_video_source(source.Value)
                break

        return Event(
            f"{uid}_{topic}_{video_source}",
            "Human Shape Detect",
            "binary_sensor",
            "motion",
            None,
            payload.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None
