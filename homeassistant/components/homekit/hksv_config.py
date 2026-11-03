"""Home Assistant recording settings derived from a validated HAP selection."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordingConfiguration:
    """Controller-selected recording settings."""

    prebuffer_ms: int
    triggers: int
    fragment_ms: int
    profile: int
    level: int
    video_bitrate: int
    iframe_ms: int
    width: int
    height: int
    fps: int
    audio_codec: int
    audio_channels: int
    audio_bitrate_mode: int
    audio_samplerate: int
    audio_bitrate: int

    @classmethod
    def from_mapping(cls, selected: dict[str, int]) -> RecordingConfiguration:
        """Convert a selection already validated by HAP-python."""
        return cls(
            prebuffer_ms=selected["prebuffer_ms"],
            triggers=selected["event_triggers"],
            fragment_ms=selected["fragment_ms"],
            profile=selected["profile"],
            level=selected["level"],
            video_bitrate=selected["video_bitrate_kbps"],
            iframe_ms=selected["iframe_interval_ms"],
            width=selected["width"],
            height=selected["height"],
            fps=selected["fps"],
            audio_codec=selected["audio_codec"],
            audio_channels=selected["audio_channels"],
            audio_bitrate_mode=selected["audio_bitrate_mode"],
            audio_samplerate=selected["audio_sample_rate"],
            audio_bitrate=selected["audio_bitrate_kbps"],
        )
