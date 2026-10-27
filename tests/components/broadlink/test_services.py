"""Tests for the Broadlink actions."""

import asyncio
from base64 import b64decode
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.services import SERVICE_LIST_COMMANDS
from homeassistant.components.broadlink.updater import BroadlinkRMUpdateManager
from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_TURN_OFF,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from . import MockSetup, get_device

ENTRANCE = "remote.entrance"
OFFICE = "remote.office"

IR_CODE = "JgAEAAECAwQ="
RF_CODE = "sgAGABERIiIzMw=="

STORED_CODES = {
    "television": {"volume_up": IR_CODE, "power": IR_CODE},
    "fan": {"speed": [IR_CODE, IR_CODE], "light": RF_CODE},
}
SORTED_NAMES = {
    "fan": ["light", "speed"],
    "television": ["power", "volume_up"],
}


def store_codes(hass_storage: dict[str, Any], name: str) -> None:
    """Put learned commands in the storage of a remote."""
    key = f"broadlink_remote_{get_device(name).mac}_codes"
    hass_storage[key] = {"version": 1, "key": key, "data": STORED_CODES}


async def list_commands(
    hass: HomeAssistant,
    entity_id: str | list[str],
    context: Context | None = None,
) -> ServiceResponse:
    """Call the action on one or more remotes."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_LIST_COMMANDS,
        {},
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
        context=context,
    )


async def make_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_setup: MockSetup,
    entity_id: str,
) -> None:
    """Make the remote stop answering so that its entity becomes unavailable."""
    mock_setup.api.check_sensors.side_effect = OSError("connection refused")
    freezer.tick(BroadlinkRMUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.fixture
async def stored_remote(hass: HomeAssistant, hass_storage: dict[str, Any]) -> MockSetup:
    """Set up a remote that has learned commands."""
    store_codes(hass_storage, "Entrance")
    mock_setup = await get_device("Entrance").setup_entry(hass)
    mock_setup.api.reset_mock()
    return mock_setup


@pytest.fixture
def no_learning_delay() -> Generator[None]:
    """Make the learning loop poll the device without waiting."""
    with patch("homeassistant.components.broadlink.remote.LEARNING_POLL_INTERVAL", 0):
        yield


async def test_action_is_registered_without_devices(hass: HomeAssistant) -> None:
    """Test the action is a response-only action that needs no device."""
    assert await async_setup_component(hass, DOMAIN, {})

    assert (
        hass.services.supports_response(DOMAIN, SERVICE_LIST_COMMANDS)
        is SupportsResponse.ONLY
    )


async def test_list_commands(hass: HomeAssistant, stored_remote: MockSetup) -> None:
    """Test the response has sorted names only and the device is not contacted."""
    response = await list_commands(hass, ENTRANCE)

    assert response == {ENTRANCE: {"devices": SORTED_NAMES}}
    assert list(response[ENTRANCE]["devices"].items()) == [
        ("fan", ["light", "speed"]),
        ("television", ["power", "volume_up"]),
    ]
    assert IR_CODE not in str(response)
    assert RF_CODE not in str(response)
    assert stored_remote.api.mock_calls == []


async def test_response_is_a_copy(
    hass: HomeAssistant, stored_remote: MockSetup
) -> None:
    """Test changing a response does not change the learned commands."""
    response = await list_commands(hass, ENTRANCE)
    response[ENTRANCE]["devices"]["television"].clear()
    response[ENTRANCE]["devices"].clear()

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": SORTED_NAMES}}


async def test_no_learned_commands(hass: HomeAssistant) -> None:
    """Test a remote without learned commands has no devices."""
    mock_setup = await get_device("Entrance").setup_entry(hass)
    mock_setup.api.reset_mock()

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": {}}}
    assert mock_setup.api.mock_calls == []


async def test_multiple_remotes(hass: HomeAssistant, stored_remote: MockSetup) -> None:
    """Test every targeted remote reports its own commands."""
    office = await get_device("Office").setup_entry(hass)
    office.api.reset_mock()

    assert await list_commands(hass, [ENTRANCE, OFFICE]) == {
        ENTRANCE: {"devices": SORTED_NAMES},
        OFFICE: {"devices": {}},
    }
    assert await list_commands(hass, OFFICE) == {OFFICE: {"devices": {}}}
    assert stored_remote.api.mock_calls == []
    assert office.api.mock_calls == []


async def test_remote_turned_off(hass: HomeAssistant, stored_remote: MockSetup) -> None:
    """Test a remote that is turned off still lists its commands."""
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTRANCE}, blocking=True
    )
    assert hass.states.get(ENTRANCE).state == STATE_OFF

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": SORTED_NAMES}}
    assert stored_remote.api.mock_calls == []


async def test_unavailable_remote_fails(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, stored_remote: MockSetup
) -> None:
    """Test an unavailable remote cannot be listed, even though its names are local."""
    await make_unavailable(hass, freezer, stored_remote, ENTRANCE)

    with pytest.raises(HomeAssistantError, match="did not match any entities"):
        await list_commands(hass, ENTRANCE)

    stored_remote.api.check_sensors.side_effect = None
    freezer.tick(BroadlinkRMUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTRANCE).state == STATE_ON

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": SORTED_NAMES}}
    stored_remote.api.send_data.assert_not_called()


async def test_unavailable_remote_is_left_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    stored_remote: MockSetup,
) -> None:
    """Test an unavailable remote is missing from the response of several remotes."""
    store_codes(hass_storage, "Office")
    office = await get_device("Office").setup_entry(hass)
    await make_unavailable(hass, freezer, office, OFFICE)

    assert await list_commands(hass, [ENTRANCE, OFFICE]) == {
        ENTRANCE: {"devices": SORTED_NAMES}
    }
    office.api.send_data.assert_not_called()


async def test_read_only_user_is_rejected(
    hass: HomeAssistant, stored_remote: MockSetup, hass_read_only_user: MockUser
) -> None:
    """Test a user who can't control the remote can't list its commands."""
    with pytest.raises(Unauthorized):
        await list_commands(hass, ENTRANCE, Context(user_id=hass_read_only_user.id))

    assert stored_remote.api.mock_calls == []


@pytest.mark.usefixtures("hass_admin_user")
async def test_non_admin_user_can_list(
    hass: HomeAssistant, stored_remote: MockSetup
) -> None:
    """Test a user who can control the remote doesn't need to be an administrator."""
    # Without another user, this one would become the owner.
    user = await hass.auth.async_create_user("User", group_ids=[GROUP_ID_USER])
    assert not user.is_admin

    assert await list_commands(hass, ENTRANCE, Context(user_id=user.id)) == {
        ENTRANCE: {"devices": SORTED_NAMES}
    }


@pytest.mark.usefixtures("no_learning_delay")
async def test_follows_learning_and_deleting(
    hass: HomeAssistant, stored_remote: MockSetup
) -> None:
    """Test the response follows learned and deleted commands before they are saved."""
    stored_remote.api.check_data.return_value = b64decode(IR_CODE)
    data = {"entity_id": ENTRANCE, "device": "new device", "command": "new command"}

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_LEARN_COMMAND, data, blocking=True
    )
    stored_remote.api.reset_mock()

    assert await list_commands(hass, ENTRANCE) == {
        ENTRANCE: {"devices": {**SORTED_NAMES, "new device": ["new command"]}}
    }

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_DELETE_COMMAND, data, blocking=True
    )

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": SORTED_NAMES}}
    assert stored_remote.api.mock_calls == []


async def test_storage_error(hass: HomeAssistant, stored_remote: MockSetup) -> None:
    """Test a failure to load the commands is not reported as an empty list."""
    with (
        patch(
            "homeassistant.components.broadlink.remote.Store.async_load",
            side_effect=HomeAssistantError("cannot load"),
        ),
        pytest.raises(HomeAssistantError, match="cannot load"),
    ):
        await list_commands(hass, ENTRANCE)

    assert await list_commands(hass, ENTRANCE) == {ENTRANCE: {"devices": SORTED_NAMES}}
    assert stored_remote.api.mock_calls == []


async def test_concurrent_listings_load_once(
    hass: HomeAssistant, stored_remote: MockSetup
) -> None:
    """Test listings that start together share one load of the storage."""
    started = asyncio.Event()
    release = asyncio.Event()
    original_load = Store.async_load

    async def slow_load(store: Store[dict[str, Any]]) -> dict[str, Any] | None:
        started.set()
        await release.wait()
        return await original_load(store)

    with patch.object(
        Store, "async_load", autospec=True, side_effect=slow_load
    ) as load:
        first = hass.async_create_task(list_commands(hass, ENTRANCE))
        await started.wait()
        second = hass.async_create_task(list_commands(hass, ENTRANCE))
        await asyncio.sleep(0)
        release.set()
        responses = await asyncio.gather(first, second)

    assert responses == [{ENTRANCE: {"devices": SORTED_NAMES}}] * 2
    # One load for the codes and one for the toggle flags.
    assert load.call_count == 2
    assert stored_remote.api.mock_calls == []


@pytest.mark.usefixtures("no_learning_delay")
async def test_learning_while_first_listing_loads(
    hass: HomeAssistant, stored_remote: MockSetup
) -> None:
    """Test learning that starts during the first load can't load the storage again."""
    started = asyncio.Event()
    release = asyncio.Event()
    original_load = Store.async_load
    stored_remote.api.check_data.return_value = b64decode(IR_CODE)

    async def slow_load(store: Store[dict[str, Any]]) -> dict[str, Any] | None:
        started.set()
        await release.wait()
        return await original_load(store)

    with patch.object(
        Store, "async_load", autospec=True, side_effect=slow_load
    ) as load:
        listing = hass.async_create_task(list_commands(hass, ENTRANCE))
        await started.wait()
        learning = hass.async_create_task(
            hass.services.async_call(
                REMOTE_DOMAIN,
                SERVICE_LEARN_COMMAND,
                {
                    "entity_id": ENTRANCE,
                    "device": "new device",
                    "command": "new command",
                },
                blocking=True,
            )
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(listing, learning)

    assert load.call_count == 2
    assert await list_commands(hass, ENTRANCE) == {
        ENTRANCE: {"devices": {**SORTED_NAMES, "new device": ["new command"]}}
    }
    stored_remote.api.send_data.assert_not_called()
