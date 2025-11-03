"""Tests for ThermoPro integration setup."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.thermopro import __init__ as thermopro
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_setup_waits_for_bluetooth_scanner(hass: HomeAssistant) -> None:
    """Ensure setup waits for Bluetooth scanners to become available."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.thermopro.__init__.bluetooth.async_scanner_count",
            return_value=0,
        ),
        pytest.raises(ConfigEntryNotReady, match="Bluetooth scanners not ready"),
    ):
        await thermopro.async_setup_entry(hass, entry)
