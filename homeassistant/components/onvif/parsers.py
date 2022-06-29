"""ONVIF event parsers."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import datetime
from typing import Any

from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from .models import Event

PARSERS: Registry[
    str, Callable[[str, Any], Coroutine[Any, Any, Event | None]]
] = Registry()


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
# pylint: disable=protected-access
async def async_parse_motion_alarm(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/MotionAlarm
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Motion Alarm",
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
async def async_parse_image_too_blurry(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBlurry/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Image Too Blurry",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooDark/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooDark/RecordingService")
# pylint: disable=protected-access
async def async_parse_image_too_dark(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooDark/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Image Too Dark",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/ImageTooBright/AnalyticsService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/ImagingService")
@PARSERS.register("tns1:VideoSource/ImageTooBright/RecordingService")
# pylint: disable=protected-access
async def async_parse_image_too_bright(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/ImageTooBright/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Image Too Bright",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:VideoSource/GlobalSceneChange/AnalyticsService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/ImagingService")
@PARSERS.register("tns1:VideoSource/GlobalSceneChange/RecordingService")
# pylint: disable=protected-access
async def async_parse_scene_change(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:VideoSource/GlobalSceneChange/*
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Global Scene Change",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:AudioAnalytics/Audio/DetectedSound")
# pylint: disable=protected-access
async def async_parse_detected_sound(uid: str, msg) -> Event | None:
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
            "Detected Sound",
            "binary_sensor",
            "sound",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/FieldDetector/ObjectsInside")
# pylint: disable=protected-access
async def async_parse_field_detector(uid: str, msg) -> Event | None:
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
            "Field Detection",
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
async def async_parse_cell_motion_detector(uid: str, msg) -> Event | None:
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
            "Cell Motion Detection",
            "binary_sensor",
            "motion",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/MotionRegionDetector/Motion")
# pylint: disable=protected-access
async def async_parse_motion_region_detector(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RuleEngine/MotionRegionDetector/Motion
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
            "Motion Region Detection",
            "binary_sensor",
            "motion",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value in ["1", "true"],
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:RuleEngine/TamperDetector/Tamper")
# pylint: disable=protected-access
async def async_parse_tamper_detector(uid: str, msg) -> Event | None:
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
            "Tamper Detection",
            "binary_sensor",
            "problem",
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/Trigger/DigitalInput")
# pylint: disable=protected-access
async def async_parse_digital_input(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/DigitalInput
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Digital Input",
            "binary_sensor",
            None,
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "true",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/Trigger/Relay")
# pylint: disable=protected-access
async def async_parse_relay(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Device/Trigger/Relay
    """
    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Relay Triggered",
            "binary_sensor",
            None,
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "active",
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Device/HardwareFailure/StorageFailure")
# pylint: disable=protected-access
async def async_parse_storage_failure(uid: str, msg) -> Event | None:
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
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/ProcessorUsage")
# pylint: disable=protected-access
async def async_parse_processor_usage(uid: str, msg) -> Event | None:
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
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None


@PARSERS.register("tns1:Monitoring/OperatingTime/LastReboot")
# pylint: disable=protected-access
async def async_parse_last_reboot(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReboot
    """
    try:
        date_time = local_datetime_or_none(
            msg.Message._value_1.Data.SimpleItem[0].Value
        )
        return Event(
            f"{uid}_{msg.Topic._value_1}",
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
# pylint: disable=protected-access
async def async_parse_last_reset(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastReset
    """
    try:
        date_time = local_datetime_or_none(
            msg.Message._value_1.Data.SimpleItem[0].Value
        )
        return Event(
            f"{uid}_{msg.Topic._value_1}",
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
# pylint: disable=protected-access
async def async_parse_backup_last(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/Backup/Last
    """

    try:
        date_time = local_datetime_or_none(
            msg.Message._value_1.Data.SimpleItem[0].Value
        )
        return Event(
            f"{uid}_{msg.Topic._value_1}",
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
# pylint: disable=protected-access
async def async_parse_last_clock_sync(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:Monitoring/OperatingTime/LastClockSynchronization
    """
    try:
        date_time = local_datetime_or_none(
            msg.Message._value_1.Data.SimpleItem[0].Value
        )
        return Event(
            f"{uid}_{msg.Topic._value_1}",
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
# pylint: disable=protected-access
async def async_parse_jobstate(uid: str, msg) -> Event | None:
    """Handle parsing event message.

    Topic: tns1:RecordingConfig/JobState
    """

    try:
        source = msg.Message._value_1.Source.SimpleItem[0].Value
        return Event(
            f"{uid}_{msg.Topic._value_1}_{source}",
            "Recording Job State",
            "binary_sensor",
            None,
            None,
            msg.Message._value_1.Data.SimpleItem[0].Value == "Active",
            EntityCategory.DIAGNOSTIC,
        )
    except (AttributeError, KeyError):
        return None
