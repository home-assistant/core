"""Test Flu Near You diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_flunearyou):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "cdc_report": {
            "level": "Low",
            "level2": "None",
            "week_date": "2020-05-16",
            "name": "Washington State",
            "fill": {"color": "#00B7B6", "opacity": 0.7},
        },
        "user_report": [
            {
                "id": 1,
                "city": "Chester(72934)",
                "place_id": "49377",
                "zip": "72934",
                "contained_by": "610",
                "latitude": REDACTED,
                "longitude": REDACTED,
                "none": 1,
                "symptoms": 0,
                "flu": 0,
                "lepto": 0,
                "dengue": 0,
                "chick": 0,
                "icon": "1",
            },
            {
                "id": 2,
                "city": "Los Angeles(90046)",
                "place_id": "23818",
                "zip": "90046",
                "contained_by": "204",
                "latitude": REDACTED,
                "longitude": REDACTED,
                "none": 2,
                "symptoms": 0,
                "flu": 0,
                "lepto": 0,
                "dengue": 0,
                "chick": 0,
                "icon": "1",
            },
            {
                "id": 3,
                "city": "Corvallis(97330)",
                "place_id": "21462",
                "zip": "97330",
                "contained_by": "239",
                "latitude": REDACTED,
                "longitude": REDACTED,
                "none": 3,
                "symptoms": 0,
                "flu": 0,
                "lepto": 0,
                "dengue": 0,
                "chick": 0,
                "icon": "1",
            },
        ],
    }
