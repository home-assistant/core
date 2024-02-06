"""Test Litter-Robot setup process."""
from unittest.mock import MagicMock, patch

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import CONFIG, VACUUM_ENTITY_ID, remove_device
from .conftest import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_unload_entry(hass: HomeAssistant, mock_account: MagicMock) -> None:
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
    ("side_effect", "expected_state"),
    (
        (LitterRobotLoginException, ConfigEntryState.SETUP_ERROR),
        (LitterRobotException, ConfigEntryState.SETUP_RETRY),
    ),
)
async def test_entry_not_setup(
    hass: HomeAssistant,
    side_effect: LitterRobotException,
    expected_state: ConfigEntryState,
) -> None:
    """Test being able to handle config entry not setup."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.hub.Account.connect",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is expected_state


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_account: MagicMock,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    config_entry = await setup_integration(hass, mock_account, VACUUM_DOMAIN)

    entity = entity_registry.entities[VACUUM_ENTITY_ID]
    assert entity.unique_id == "LR3C012345-litter_box"

    device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), device_entry.id, config_entry.entry_id
        )
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(litterrobot.DOMAIN, "test-serial", "remove-serial")},
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), dead_device_entry.id, config_entry.entry_id
        )
        is True
    )
