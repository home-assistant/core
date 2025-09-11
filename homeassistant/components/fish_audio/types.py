"""Type definitions for the Fish Audio integration."""

from __future__ import annotations

from typing import TypedDict

from fish_audio_sdk import Session

from homeassistant.config_entries import ConfigEntry

type FishAudioConfigEntry = ConfigEntry[Session]


class MainConfigData(TypedDict):
    """Main Fish Audio configuration data."""

    api_key: str
    user_id: str


class TTSConfigData(TypedDict, total=False):
    """Fish Audio TTS subentry configuration data."""

    voice_id: str
    backend: str
    language: str
    self_only: bool
    sort_by: str
    name: str


class UserInput(TypedDict):
    """User input for the Fish Audio config flow."""

    api_key: str


class SubentryInitUserInput(TypedDict, total=False):
    """User input for the Fish Audio subentry init step."""

    name: str
    language: str
    self_only: bool
    sort_by: str


class SubentryModelUserInput(TypedDict):
    """User input for the Fish Audio subentry model step."""

    voice_id: str
    backend: str
