"""Shared test fixtures for SunSynk integration tests."""

from __future__ import annotations

import asyncio
import json
import os
import pathlib

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.loader import DATA_INTEGRATIONS, Integration
from homeassistant.runner import HassEventLoopPolicy

INTEGRATION_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "sunsynk"


# Patch HassEventLoopPolicy.get_event_loop to create a loop when missing,
# matching the default asyncio policy behaviour. Without this, the
# verify_cleanup and enable_event_loop_debug fixtures from
# pytest-homeassistant-custom-component crash on Python 3.14 because
# HassEventLoopPolicy.get_event_loop raises RuntimeError when there is
# no current loop (between test teardown and the next test's setup).
_orig_get_event_loop = HassEventLoopPolicy.get_event_loop


def _get_event_loop_safe(self: HassEventLoopPolicy) -> asyncio.AbstractEventLoop:
    try:
        return _orig_get_event_loop(self)
    except RuntimeError:
        loop = self.new_event_loop()
        self.set_event_loop(loop)
        return loop


HassEventLoopPolicy.get_event_loop = _get_event_loop_safe  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def register_sunsynk_integration(hass: HomeAssistant) -> None:
    """Register the sunsynk integration so the HA loader can find it."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())
    top_level_files = set(os.listdir(INTEGRATION_DIR))

    integration = Integration(
        hass,
        pkg_path="custom_components.sunsynk",
        file_path=INTEGRATION_DIR,
        manifest=manifest,
        top_level_files=top_level_files,
    )

    cache: dict = hass.data.setdefault(DATA_INTEGRATIONS, {})
    cache["sunsynk"] = integration
