"""Axis network device abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TRIGGER_TIME,
    CONF_USERNAME,
)

from ..const import (
    CONF_STREAM_PROFILE,
    CONF_VIDEO_SOURCE,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_TRIGGER_TIME,
    DEFAULT_VIDEO_SOURCE,
)


@dataclass
class AxisConfig:
    """Represent a Axis config entry."""

    entry: ConfigEntry

    protocol: str
    host: str
    port: int
    username: str
    password: str
    model: str
    name: str

    # Options

    stream_profile: str
    """Option defining what stream profile camera platform should use."""
    trigger_time: int
    """Option defining minimum number of seconds to keep trigger high."""
    video_source: str
    """Option defining what video source camera platform should use."""

    @classmethod
    def from_config_entry(cls, config_entry: ConfigEntry) -> Self:
        """Create object from config entry."""
        config = config_entry.data
        options = config_entry.options
        return cls(
            entry=config_entry,
            protocol=config.get(CONF_PROTOCOL, "http"),
            host=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
            model=config[CONF_MODEL],
            name=config[CONF_NAME],
            stream_profile=options.get(CONF_STREAM_PROFILE, DEFAULT_STREAM_PROFILE),
            trigger_time=options.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME),
            video_source=options.get(CONF_VIDEO_SOURCE, DEFAULT_VIDEO_SOURCE),
        )
