"""Type definitions for the Fish Audio integration."""

from fishaudio import AsyncFishAudio

from homeassistant.config_entries import ConfigEntry

type FishAudioConfigEntry = ConfigEntry[AsyncFishAudio]
