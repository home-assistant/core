"""Test voice assistant commands."""

import pytest
from homeassistant.components.voice_assistant import process_voice_input
from homeassistant.core import HomeAssistant


def test_voice_assistant_integration(hass):
    voice_input = "turn on the lights"
    expected_output = "Lights turned on"
    assert process_voice_input(hass, voice_input) == expected_output
