"""Test Litter-Robot setup process."""
from unittest.mock import patch

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import pytest

from homeassistant.components import litterrobot

from .common import CONFIG
from .conftest import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(hass, mock_account):
    """Test being able to unload an entry."""
    entry = await setup_integration(hass, mock_account)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[litterrobot.DOMAIN] == {}


@pytest.mark.parametrize(
    "exception",
    (LitterRobotLoginException, LitterRobotException),
)
async def test_entry_not_setup(hass, exception):
    """Test being able to handle config entry not setup."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "pylitterbot.Account.connect",
        side_effect=exception,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
