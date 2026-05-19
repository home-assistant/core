"""Types for the FlowSpeech integration."""

from flowspeech_sdk import FlowSpeechClient

from homeassistant.config_entries import ConfigEntry

type FlowSpeechConfigEntry = ConfigEntry[FlowSpeechClient]
