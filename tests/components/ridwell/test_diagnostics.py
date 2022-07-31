"""Test Ridwell diagnostics."""
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_ridwell):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
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
        ]
    }
