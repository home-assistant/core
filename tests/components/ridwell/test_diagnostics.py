"""Test Ridwell diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 2,
            "domain": "ridwell",
            "title": REDACTED,
            "data": {"username": REDACTED, "password": REDACTED},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "data": [
            {
                "_async_request": None,
                "event_id": "event_123",
                "pickup_date": {
                    "__type": "<class 'datetime.date'>",
                    "isoformat": "2022-01-24",
                },
                "pickups": [
                    {
                        "name": "Plastic Film",
                        "offer_id": "offer_123",
                        "priority": 1,
                        "product_id": "product_123",
                        "quantity": 1,
                        "category": {
                            "__type": "<enum 'PickupCategory'>",
                            "repr": "<PickupCategory.STANDARD: 'standard'>",
                        },
                    }
                ],
                "state": {
                    "__type": "<enum 'EventState'>",
                    "repr": "<EventState.INITIALIZED: 'initialized'>",
                },
            }
        ],
    }
