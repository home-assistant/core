"""Adapt Home Assistant recording state to HAP-python's HKSV API."""

import base64
from dataclasses import dataclass
from typing import Any

from pyhap import hds, hksv_recording as hk, tlv
from pyhap.characteristic import Characteristic
from pyhap.service import Service


def b64(data: bytes) -> str:
    """Encode a characteristic value as base64."""
    return base64.b64encode(data).decode("ascii")


@dataclass(frozen=True)
class RecordingCapabilities:
    """Supported settings for the configured recorder."""

    audio_codec: int
    audio_sample_rate: int
    prebuffer_ms: int = 4000
    fragment_ms: int = 4000
    event_triggers: int = 1
    audio_channels: int = 1
    audio_bitrate_mode: int = 0
    resolutions: tuple[tuple[int, int, int], ...] = ()
    profiles: tuple[int, ...] = ()
    levels: tuple[int, ...] = ()

    def supported(self) -> tuple[str, str, str]:
        """Encode the three advertised recording configurations."""
        general = hk.SupportedRecordingConfiguration(
            prebuffer_length_ms=self.prebuffer_ms,
            event_triggers=self.event_triggers,
            media_containers=[
                hk.MediaContainerConfiguration(fragment_length_ms=self.fragment_ms)
            ],
        )
        video = hk.VideoCodecConfiguration(
            codec_type=hk.VideoCodecType.H264,
            profile=list(self.profiles),
            level=list(self.levels),
            bitrate_kbps=0,
            iframe_interval_ms=0,
            attributes=[hk.VideoAttributes(*r) for r in self.resolutions],
        )
        audio = hk.AudioCodecConfiguration(
            codec_type=hk.AudioCodecType(self.audio_codec),
            channels=self.audio_channels,
            bitrate_mode=hk.BitRateMode(self.audio_bitrate_mode),
            sample_rate=hk.AudioSampleRate(self.audio_sample_rate),
        )
        return (
            b64(general.encode()),
            b64(hk.encode_supported_video([video])),
            b64(hk.encode_supported_audio([audio])),
        )


def parse_selected(raw: bytes, caps: RecordingCapabilities) -> dict[str, int]:
    """Validate the library-decoded selection against advertised capabilities."""
    try:
        selected = hk.SelectedRecordingConfiguration.decode(raw)
        rec, video, audio = selected.recording, selected.video, selected.audio
        if len(rec.media_containers) != 1 or len(video.attributes) != 1:
            raise ValueError("Expected one container and resolution")
        container, attr = rec.media_containers[0], video.attributes[0]
        if (
            container.container_type != hk.MediaContainerType.FRAGMENTED_MP4
            or video.codec_type != hk.VideoCodecType.H264
            or not 0 < rec.prebuffer_length_ms <= caps.prebuffer_ms
            or not rec.event_triggers
            or rec.event_triggers & ~caps.event_triggers
            or container.fragment_length_ms != caps.fragment_ms
            or (attr.width, attr.height, attr.frame_rate) not in caps.resolutions
            or not isinstance(video.profile, int)
            or video.profile not in caps.profiles
            or not isinstance(video.level, int)
            or video.level not in caps.levels
            or audio.codec_type != caps.audio_codec
            or audio.channels != caps.audio_channels
            or audio.bitrate_mode != caps.audio_bitrate_mode
            or audio.sample_rate != caps.audio_sample_rate
            or not 1 <= video.bitrate_kbps <= 10000
            or not 1 <= video.iframe_interval_ms <= 4000
            or not 1 <= audio.max_audio_bitrate_kbps <= 512
        ):
            raise ValueError("Unsupported selected recording configuration")
        result = {
            "prebuffer_ms": rec.prebuffer_length_ms,
            "event_triggers": rec.event_triggers,
            "fragment_ms": container.fragment_length_ms,
            "width": attr.width,
            "height": attr.height,
            "fps": attr.frame_rate,
            "profile": video.profile,
            "level": video.level,
            "video_bitrate_kbps": video.bitrate_kbps,
            "iframe_interval_ms": video.iframe_interval_ms,
            "audio_codec": audio.codec_type,
            "audio_channels": audio.channels,
            "audio_bitrate_mode": audio.bitrate_mode,
            "audio_sample_rate": audio.sample_rate,
            "audio_bitrate_kbps": audio.max_audio_bitrate_kbps,
        }
    except (KeyError, IndexError, TypeError, OverflowError) as err:
        raise ValueError("Invalid selected recording configuration") from err
    else:
        return result


@dataclass(frozen=True)
class RecordingServices:
    """Detached HAP services and their controlled characteristics."""

    recording: Service
    operating: Service
    transport: Service
    active: Characteristic
    audio_active: Characteristic
    selected: Characteristic
    camera_active: Characteristic
    event_snapshots: Characteristic
    periodic_snapshots: Characteristic
    setup: Characteristic


def make_services(driver: Any, caps: RecordingCapabilities) -> RecordingServices:
    """Construct detached services from the library's official catalog."""
    loader = driver.loader
    recording = loader.get_service("CameraRecordingManagement")
    operating = loader.get_service("CameraOperatingMode")
    transport = loader.get_service("DataStreamTransportManagement")
    recording.add_characteristic(loader.get_char("RecordingAudioActive"))
    operating.add_characteristic(loader.get_char("PeriodicSnapshotsActive"))
    # Preserve characteristic ordering when assigning new IIDs.
    for service, names in (
        (
            recording,
            (
                "Active",
                "RecordingAudioActive",
                "SelectedCameraRecordingConfiguration",
                "SupportedCameraRecordingConfiguration",
                "SupportedVideoRecordingConfiguration",
                "SupportedAudioRecordingConfiguration",
            ),
        ),
        (
            operating,
            ("HomeKitCameraActive", "EventSnapshotsActive", "PeriodicSnapshotsActive"),
        ),
    ):
        service.characteristics.sort(key=lambda char: names.index(char.display_name))
    general, video, audio = caps.supported()
    for name, value in (
        ("SupportedCameraRecordingConfiguration", general),
        ("SupportedVideoRecordingConfiguration", video),
        ("SupportedAudioRecordingConfiguration", audio),
        ("Active", 0),
        ("RecordingAudioActive", 0),
    ):
        recording.get_characteristic(name).set_value(value, should_notify=False)
    for name in (
        "HomeKitCameraActive",
        "EventSnapshotsActive",
        "PeriodicSnapshotsActive",
    ):
        operating.get_characteristic(name).set_value(1, should_notify=False)
    transport.get_characteristic("Version").set_value("1.0", should_notify=False)
    transport.get_characteristic("SupportedDataStreamTransportConfiguration").set_value(
        b64(tlv.encode(b"\x01", tlv.encode(b"\x01", hds.TRANSPORT_TYPE_TCP))),
        should_notify=False,
    )
    return RecordingServices(
        recording=recording,
        operating=operating,
        transport=transport,
        active=recording.get_characteristic("Active"),
        audio_active=recording.get_characteristic("RecordingAudioActive"),
        selected=recording.get_characteristic("SelectedCameraRecordingConfiguration"),
        camera_active=operating.get_characteristic("HomeKitCameraActive"),
        event_snapshots=operating.get_characteristic("EventSnapshotsActive"),
        periodic_snapshots=operating.get_characteristic("PeriodicSnapshotsActive"),
        setup=transport.get_characteristic("SetupDataStreamTransport"),
    )
