"""Test ReCollect Waste diagnostics."""
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass, config_entry, hass_client, setup_recollect_waste
):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": config_entry.as_dict(),
        "data": [
            {
                "date": {
                    "__type": "<class 'datetime.date'>",
                    "isoformat": "2022-01-23",
                },
                "pickup_types": [
                    {"name": "garbage", "friendly_name": "Trash Collection"}
                ],
                "area_name": "The Sun",
            }
        ],
    }
