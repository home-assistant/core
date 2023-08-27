"""Test august diagnostics."""
from unittest.mock import ANY

from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await async_init_integration(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "data": {
            "aux_properties": {"number": [], "select": [], "sensor": [], "switch": []},
            "devices": {},
            "net_resources": [],
            "nodes": {
                "binary_sensor": [],
                "climate": [],
                "cover": [],
                "fan": [],
                "light": [],
                "lock": [],
                "sensor": [],
                "switch": [],
            },
            "programs": {
                "binary_sensor": [],
                "cover": [],
                "fan": [],
                "lock": [],
                "switch": [],
            },
            "root": ANY,
            "root_nodes": {"button": []},
            "variables": {"number": [], "sensor": []},
        },
        "entry": {"options": {}, "title": "Mock Title"},
    }
