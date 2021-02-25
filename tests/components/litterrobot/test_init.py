"""Test Litter-Robot setup process."""
from unittest.mock import patch

from pylitterbot.exceptions import LitterRobotException

from homeassistant.components import litterrobot
from homeassistant.setup import async_setup_component

from .common import CONFIG

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, litterrobot.DOMAIN, {}) is True
    assert await litterrobot.async_unload_entry(hass, entry)
    assert hass.data[litterrobot.DOMAIN] == {}


async def test_not_ready(hass):
    """Test being able to handle config entry not ready."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.LitterRobotHub.login",
        side_effect=LitterRobotException,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
