"""Test removal when the integration's dependencies were not loaded."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.storage import EnergyHistoryStore
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def use_recorder() -> None:
    """Leave recorder unloaded, as when removing a disabled entry after startup."""


async def test_remove_disabled_entry_without_recorder(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Remove a previously registered site without requiring recorder setup."""
    entry = MockConfigEntry(domain=DOMAIN, disabled_by=ConfigEntryDisabler.USER)
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "123456")},
    )
    store = EnergyHistoryStore(hass, entry.entry_id, "123456")
    await store.async_save({"start": 0, "statistics": {}})
    assert "recorder" not in hass.config.components
    with patch(
        "homeassistant.components.tesla_fleet.get_recorder_instance"
    ) as get_recorder:
        await hass.config_entries.async_remove(entry.entry_id)
    get_recorder.assert_not_called()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert store.key not in hass_storage
