"""Type definitions for the Fish Audio integration."""

from __future__ import annotations

from fish_audio_sdk import Session

from homeassistant.config_entries import ConfigEntry

type FishAudioConfigEntry = ConfigEntry[Session]
