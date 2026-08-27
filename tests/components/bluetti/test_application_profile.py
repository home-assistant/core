"""Tests for profile/application_profile.py."""

import pytest

from homeassistant.components.bluetti.profile.application_profile import (
    ApplicationProfile,
)
from homeassistant.core import HomeAssistant


def test_active_profile_prefixes_config_filename() -> None:
    """Active profile prefixes config filename."""
    profile = ApplicationProfile(active="staging")
    assert profile._ApplicationProfile__configFile == "application-staging.yaml"


async def test_load_config_missing_file_raises_and_logs(hass: HomeAssistant) -> None:
    """Load config missing file raises and logs."""
    profile = ApplicationProfile(active="does-not-exist")

    with pytest.raises(OSError):
        await profile.load_config(hass)
