"""Test ReCollect Waste diagnostics."""

import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERVICE_ID

from tests.common import ANY, MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("setup_config_entry")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 2,
            "minor_version": 1,
            "domain": "recollect_waste",
            "title": REDACTED,
            "data": {"place_id": REDACTED, "service_id": TEST_SERVICE_ID},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
            "created_at": ANY,
            "modified_at": ANY,
            "discovery_keys": {},
            "subentries": [],
        },
        "data": [
            {
                "date": {
                    "__type": "<class 'datetime.date'>",
                    "isoformat": "2022-01-23",
                },
                "pickup_types": [
                    {"name": "garbage", "friendly_name": "Trash Collection"}
                ],
                "area_name": REDACTED,
            }
        ],
    }
