"""Test the legacy stt setup."""
from __future__ import annotations

from pathlib import Path

import pytest

from homeassistant.components.stt import Provider
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import mock_stt_platform


async def test_invalid_platform(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test platform setup with an invalid platform."""
    await async_load_platform(
        hass,
        "stt",
        "bad_stt",
        {"stt": [{"platform": "bad_stt"}]},
        hass_config={"stt": [{"platform": "bad_stt"}]},
    )
    await hass.async_block_till_done()

    assert "Unknown speech to text platform specified" in caplog.text


async def test_platform_setup_with_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test platform setup with an error during setup."""

    async def async_get_engine(
        hass: HomeAssistant,
        config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> Provider:
        """Raise exception during platform setup."""
        raise Exception("Setup error")  # pylint: disable=broad-exception-raised

    mock_stt_platform(hass, tmp_path, "bad_stt", async_get_engine=async_get_engine)

    await async_load_platform(
        hass,
        "stt",
        "bad_stt",
        {},
        hass_config={"stt": [{"platform": "bad_stt"}]},
    )
    await hass.async_block_till_done()

    assert "Error setting up platform: bad_stt" in caplog.text
