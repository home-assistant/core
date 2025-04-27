"""ONVIF event parsers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import dataclasses
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
@PARSERS.register("tns1:Device/Trigger/tnshik:AlarmIn")
async def async_parse_motion_alarm(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/MotionAlarm
    """
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


@PARSERS.register("tns1:VideoSource/ImageTooBlurry/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBlurry/RecordingService")
async def async_parse_image_too_blurry(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBlurry/*
    """
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


@PARSERS.register("tns1:VideoSource/ImageTooDark/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/RecordingService")
async def async_parse_image_too_dark(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooDark/*
    """
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


@PARSERS.register("tns1:VideoSource/ImageTooBright/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/RecordingService")
async def async_parse_image_too_bright(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBright/*
    """
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


@PARSERS.register("tns1:VideoSource/GlobalSceneChange/AnalyticsService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/ImagingService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/RecordingService")
async def async_parse_scene_change(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/GlobalSceneChange/*
    """
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


@PARSERS.register("tns1:AudioAnalytics/Audio/DetectedSound")
async def async_parse_detected_sound(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:AudioAnalytics/Audio/DetectedSound
    """
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


@PARSERS.register("tns1:RuleEngine/FieldDetector/ObjectsInside")
async def async_parse_field_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/FieldDetector/ObjectsInside
    """
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
        "Field Detection",
        "binary_sensor",
        "motion",
        None,
        payload.Data.SimpleItem[0].Value == "true",
    )


@PARSERS.register("tns1:RuleEngine/CellMotionDetector/Motion")
async def async_parse_cell_motion_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/CellMotionDetector/Motion
    """
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


@PARSERS.register("tns1:RuleEngine/MotionRegionDetector/Motion")
async def async_parse_motion_region_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MotionRegionDetector/Motion
    """
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


@PARSERS.register("tns1:RuleEngine/TamperDetector/Tamper")
async def async_parse_tamper_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/TamperDetector/Tamper
    """
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


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/DogCatDetect")
async def async_parse_dog_cat_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/DogCatDetect
    """
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


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/VehicleDetect")
async def async_parse_vehicle_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/VehicleDetect
    """
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


_TAPO_EVENT_TEMPLATES: dict[str, Event] = {
    "IsVehicle": Event(
        uid="",
        name="Vehicle Detection",
        platform="binary_sensor",
        device_class="motion",
    ),
    "IsPeople": Event(
        uid="", name="Person Detection", platform="binary_sensor", device_class="motion"
    ),
    "IsPet": Event(
        uid="", name="Pet Detection", platform="binary_sensor", device_class="motion"
    ),
    "IsLineCross": Event(
        uid="",
        name="Line Detector Crossed",
        platform="binary_sensor",
        device_class="motion",
    ),
    "IsTamper": Event(
        uid="", name="Tamper Detection", platform="binary_sensor", device_class="tamper"
    ),
    "IsIntrusion": Event(
        uid="",
        name="Intrusion Detection",
        platform="binary_sensor",
        device_class="safety",
    ),
}


@PARSERS.register("tns1:RuleEngine/CellMotionDetector/Intrusion")
@PARSERS.register("tns1:RuleEngine/CellMotionDetector/LineCross")
@PARSERS.register("tns1:RuleEngine/CellMotionDetector/People")
@PARSERS.register("tns1:RuleEngine/CellMotionDetector/Tamper")
@PARSERS.register("tns1:RuleEngine/CellMotionDetector/TpSmartEvent")
@PARSERS.register("tns1:RuleEngine/PeopleDetector/People")
@PARSERS.register("tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent")
async def async_parse_tplink_detector(uid: str, msg) -> Event | None:
    """Handle parsing tplink smart event messages.

    Topic: tns1:RuleEngine/CellMotionDetector/Intrusion
    Topic: tns1:RuleEngine/CellMotionDetector/LineCross
    Topic: tns1:RuleEngine/CellMotionDetector/People
    Topic: tns1:RuleEngine/CellMotionDetector/Tamper
    Topic: tns1:RuleEngine/CellMotionDetector/TpSmartEvent
    Topic: tns1:RuleEngine/PeopleDetector/People
    Topic: tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent
    """
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

    for item in payload.Data.SimpleItem:
        event_template = _TAPO_EVENT_TEMPLATES.get(item.Name, None)
        if event_template is None:
            continue

        return dataclasses.replace(
            event_template,
            uid=f"{uid}_{topic}_{video_source}_{video_analytics}_{rule}",
            value=item.Value == "true",
        )

    return None


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/PeopleDetect")
async def async_parse_person_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/PeopleDetect
    """
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


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/FaceDetect")
async def async_parse_face_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/FaceDetect
    """
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


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/Visitor")
async def async_parse_visitor_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/Visitor
    """
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


@PARSERS.register("tns1:RuleEngine/MyRuleDetector/Package")
async def async_parse_package_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MyRuleDetector/Package
    """
    video_source = ""
    topic, payload = extract_message(msg)
    for source in payload.Source.SimpleItem:
        if source.Name == "Source":
            video_source = _normalize_video_source(source.Value)

    return Event(
        f"{uid}_{topic}_{video_source}",
        "Package Detection",
        "binary_sensor",
        "occupancy",
        None,
        payload.Data.SimpleItem[0].Value == "true",
    )


@PARSERS.register("tns1:Device/Trigger/DigitalInput")
async def async_parse_digital_input(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/DigitalInput
    """
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


@PARSERS.register("tns1:Device/Trigger/Relay")
async def async_parse_relay(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/Relay
    """
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


@PARSERS.register("tns1:Device/HardwareFailure/StorageFailure")
async def async_parse_storage_failure(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/HardwareFailure/StorageFailure
    """
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


@PARSERS.register("tns1:Monitoring/ProcessorUsage")
async def async_parse_processor_usage(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/ProcessorUsage
    """
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


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReboot")
async def async_parse_last_reboot(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReboot
    """
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


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReset")
async def async_parse_last_reset(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReset
    """
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


@PARSERS.register("tns1:Monitoring/Backup/Last")
async def async_parse_backup_last(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/Backup/Last
    """
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


@PARSERS.register("tns1:Monitoring/OperatingTime/LastClockSynchronization")
async def async_parse_last_clock_sync(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastClockSynchronization
    """
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


@PARSERS.register("tns1:RecordingConfig/JobState")
async def async_parse_jobstate(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RecordingConfig/JobState
    """

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


@PARSERS.register("tns1:RuleEngine/LineDetector/Crossed")
async def async_parse_linedetector_crossed(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/LineDetector/Crossed
    """
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


@PARSERS.register("tns1:RuleEngine/CountAggregation/Counter")
async def async_parse_count_aggregation_counter(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/CountAggregation/Counter
    """
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


@PARSERS.register("tns1:UserAlarm/IVA/HumanShapeDetect")
async def async_parse_human_shape_detect(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:UserAlarm/IVA/HumanShapeDetect
    """
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
