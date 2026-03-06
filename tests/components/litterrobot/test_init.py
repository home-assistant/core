"""Test Litter-Robot setup process."""

from unittest.mock import MagicMock, patch

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import pytest

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_START,
    VacuumActivity,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import ACCOUNT_USER_ID, CONFIG, DOMAIN, VACUUM_ENTITY_ID
from .conftest import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_unload_entry(hass: HomeAssistant, mock_account: MagicMock) -> None:
    """Test being able to unload an entry."""
    entry = await setup_integration(hass, mock_account, VACUUM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == VacuumActivity.DOCKED

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_START,
        {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
        blocking=True,
    )
    mock_account.robots[0].start_cleaning.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LitterRobotLoginException, ConfigEntryState.SETUP_ERROR),
        (LitterRobotException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_entry_not_setup(
    hass: HomeAssistant,
    side_effect: LitterRobotException,
    expected_state: ConfigEntryState,
) -> None:
    """Test being able to handle config entry not setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.coordinator.Account.connect",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is expected_state


async def test_unique_id_migration(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test that legacy entries get unique_id set during migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        version=1,
        minor_version=1,
    )
    assert entry.unique_id is None
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.Account",
        return_value=mock_account,
    ), patch(
        "homeassistant.components.litterrobot.coordinator.Account",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == ACCOUNT_USER_ID
    assert entry.minor_version == 2
    mock_account.disconnect.assert_called_once()


async def test_unique_id_migration_unsupported_version(
    hass: HomeAssistant,
) -> None:
    """Test that migration fails for entries with version > 1."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_unique_id_migration_conflict(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test that migration skips unique_id when another entry owns it."""
    # First entry already has the unique_id
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    ).add_to_hass(hass)

    # Second entry is legacy (no unique_id)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        version=1,
        minor_version=1,
    )
    assert entry.unique_id is None
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.Account",
        return_value=mock_account,
    ), patch(
        "homeassistant.components.litterrobot.coordinator.Account",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id is None
    assert entry.minor_version == 2


async def test_unique_id_migration_connection_failure(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test that migration succeeds without unique_id when API is unreachable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.Account.connect",
        side_effect=LitterRobotException,
    ), patch(
        "homeassistant.components.litterrobot.coordinator.Account",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id is None
    assert entry.minor_version == 2
    assert entry.state is ConfigEntryState.LOADED


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
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test-serial", "remove-serial")},
    )
    response = await client.remove_device(dead_device_entry.id, config_entry.entry_id)
    assert response["success"]
