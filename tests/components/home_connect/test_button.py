"""Tests for home_connect button entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfCommands,
    CommandKey,
    EventMessage,
    HomeAppliance,
)
from aiohomeconnect.model.command import Command
from aiohomeconnect.model.error import HomeConnectApiError
from aiohomeconnect.model.event import ArrayOfEvents, EventType
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BUTTON]


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize(
    ("appliance", "keys_to_check"),
    [
        (
            "Washer",
            (CommandKey.BSH_COMMON_PAUSE_PROGRAM,),
        )
    ],
    indirect=["appliance"],
)
async def test_connected_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    keys_to_check: tuple,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_available_commands_original_mock = client.get_available_commands
    get_all_programs_mock = client.get_all_programs

    async def get_available_commands_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_available_commands_original_mock.side_effect(ha_id)

    async def get_all_programs_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_all_programs_mock.side_effect(ha_id)

    client.get_available_commands = AsyncMock(
        side_effect=get_available_commands_side_effect
    )
    client.get_all_programs = AsyncMock(side_effect=get_all_programs_side_effect)
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_available_commands = get_available_commands_original_mock
    client.get_all_programs = get_all_programs_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    assert entity_registry.async_get_entity_id(
        Platform.BUTTON,
        DOMAIN,
        f"{appliance.ha_id}-StopProgram",
    )
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.BUTTON,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for key in (*keys_to_check, "StopProgram"):
        assert entity_registry.async_get_entity_id(
            Platform.BUTTON,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_button_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if button entities availability are based on the appliance connection state."""
    entity_ids = [
        "button.washer_pause_program",
        "button.washer_stop_program",
    ]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "method_call", "expected_kwargs"),
    [
        (
            "button.washer_pause_program",
            "put_command",
            {"command_key": CommandKey.BSH_COMMON_PAUSE_PROGRAM, "value": True},
        ),
        ("button.washer_stop_program", "stop_program", {}),
    ],
)
async def test_button_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    method_call: str,
    expected_kwargs: dict[str, Any],
    appliance: HomeAppliance,
) -> None:
    """Test if button entities availability are based on the appliance connection state."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state != STATE_UNAVAILABLE

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    getattr(client, method_call).assert_called_with(appliance.ha_id, **expected_kwargs)


async def test_command_button_exception(
    hass: HomeAssistant,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test if button entities availability are based on the appliance connection state."""
    entity_id = "button.washer_pause_program"

    client_with_exception.get_available_commands = AsyncMock(
        return_value=ArrayOfCommands(
            [
                Command(
                    CommandKey.BSH_COMMON_PAUSE_PROGRAM,
                    "Pause Program",
                )
            ]
        )
    )
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state != STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError, match=r"Error.*executing.*command"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_stop_program_button_exception(
    hass: HomeAssistant,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test if button entities availability are based on the appliance connection state."""
    entity_id = "button.washer_stop_program"

    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state != STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError, match=r"Error.*stop.*program"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
