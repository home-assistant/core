"""Test Litter-Robot setup process."""
from unittest.mock import patch

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import pytest

from homeassistant.components import litterrobot
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_START,
    STATE_DOCKED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID

from .common import CONFIG, VACUUM_ENTITY_ID
from .conftest import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(hass, mock_account):
    """Test being able to unload an entry."""
    entry = await setup_integration(hass, mock_account, VACUUM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_START,
        {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
        blocking=True,
    )
    getattr(mock_account.robots[0], "start_cleaning").assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[litterrobot.DOMAIN] == {}


@pytest.mark.parametrize(
    "side_effect,expected_state",
    (
        (LitterRobotLoginException, ConfigEntryState.SETUP_ERROR),
        (LitterRobotException, ConfigEntryState.SETUP_RETRY),
    ),
)
async def test_entry_not_setup(hass, side_effect, expected_state):
    """Test being able to handle config entry not setup."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "pylitterbot.Account.connect",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is expected_state
