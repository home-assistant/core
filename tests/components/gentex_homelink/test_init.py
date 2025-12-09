"""Test that the integration is initialized correctly."""

from unittest.mock import patch

from homeassistant.components import gentex_homelink
from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
) -> None:
    """Test the entry can be loaded and unloaded."""
    with patch("homeassistant.components.gentex_homelink.MQTTProvider", autospec=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=None,
            version=1,
            data={"auth_implementation": "gentex_homelink"},
        )
        entry.add_to_hass(hass)

        assert await async_setup_component(hass, DOMAIN, {}) is True, (
            "Component is not set up"
        )

        assert await gentex_homelink.async_unload_entry(hass, entry), (
            "Component not unloaded"
        )
