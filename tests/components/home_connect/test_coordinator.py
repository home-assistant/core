"""Test for Home Connect coordinator."""

from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfSettings,
    ArrayOfStatus,
    Event,
    EventKey,
    EventMessage,
    EventType,
)
from aiohomeconnect.model.error import (
    EventStreamInterruptedError,
    HomeConnectApiError,
    HomeConnectError,
    HomeConnectRequestError,
)
import pytest

from homeassistant.components.home_connect.coordinator import HomeConnectConfigEntry
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert cast(HomeConnectConfigEntry, config_entry).runtime_data.data


async def test_coordinator_update_failing_get_appliances(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test that the coordinator raises ConfigEntryNotReady when it fails to get appliances."""
    client_with_exception.get_home_appliances.return_value = None
    client_with_exception.get_home_appliances.side_effect = HomeConnectError()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failing_get_settings_status(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test that although is not possible to get settings and status, the config entry is loaded.

    This is for cases where some appliances are reachable and some are not in the same configuration entry.
    """
    # Get home appliances does pass at client_with_exception.get_home_appliances mock, so no need to mock it again
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    assert cast(HomeConnectConfigEntry, config_entry).runtime_data.data


@pytest.mark.parametrize(
    ("event_type", "event_key"),
    [
        (EventType.STATUS, EventKey.BSH_COMMON_STATUS_DOOR_STATE),
        (EventType.NOTIFY, EventKey.BSH_COMMON_SETTING_POWER_STATE),
        (EventType.EVENT, EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY),
    ],
)
async def test_event_listener(
    event_type: EventType,
    event_key: EventKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test that the event listener works."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    listener = MagicMock()
    coordinator = cast(HomeConnectConfigEntry, config_entry).runtime_data
    remove_listener = coordinator.async_add_listener(
        listener, (appliance_ha_id, event_key)
    )

    event_message = EventMessage(
        appliance_ha_id,
        event_type,
        ArrayOfEvents(
            [
                Event(
                    event_key,
                    0,
                    "",
                    "",
                    "some value",
                )
            ],
        ),
    )
    await client.add_events([event_message])
    await hass.async_block_till_done()

    listener.assert_called_once()

    remove_listener()
    await client.add_events([event_message])
    await hass.async_block_till_done()

    listener.assert_called_once()
    assert coordinator._home_appliances_event_listeners == {}


@pytest.mark.parametrize(
    ("event_type", "event_key"),
    [
        (EventType.STATUS, EventKey.UNKNOWN),
        (EventType.NOTIFY, EventKey.UNKNOWN),
        (EventType.EVENT, EventKey.UNKNOWN),
    ],
)
async def test_event_listener_ignore_unknowns(
    event_type: EventType,
    event_key: EventKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test that the event listener works."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    listener = AsyncMock()
    coordinator = cast(HomeConnectConfigEntry, config_entry).runtime_data
    coordinator.async_add_listener(listener, (appliance_ha_id, event_key))

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                event_type,
                ArrayOfEvents(
                    [
                        Event(
                            event_key,
                            0,
                            "",
                            "",
                            "some value",
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()

    listener.assert_not_awaited()


async def tests_receive_setting_and_status_for_first_time_at_events(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test that the event listener is capable of receiving settings and status for the first time."""
    client.get_setting = AsyncMock(return_value=ArrayOfSettings([]))
    client.get_status = AsyncMock(return_value=ArrayOfStatus([]))

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.NOTIFY,
                ArrayOfEvents(
                    [
                        Event(
                            EventKey.LAUNDRY_CARE_WASHER_SETTING_I_DOS_1_BASE_LEVEL,
                            0,
                            "",
                            "",
                            "some value",
                        )
                    ],
                ),
            ),
            EventMessage(
                appliance_ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
                            0,
                            "",
                            "",
                            "some value",
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()
    assert len(config_entry._background_tasks) == 1
    assert config_entry.state == ConfigEntryState.LOADED


async def test_event_listener_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test that the configuration entry is reloaded when the event stream raises an API error."""
    client_with_exception.stream_all_events = MagicMock(
        side_effect=HomeConnectApiError("error.key", "error description")
    )

    with patch.object(
        ConfigEntries,
        "async_schedule_reload",
    ) as mock_schedule_reload:
        await integration_setup(client_with_exception)
        await hass.async_block_till_done()

    client_with_exception.stream_all_events.assert_called_once()
    mock_schedule_reload.assert_called_once_with(config_entry.entry_id)
    assert not config_entry._background_tasks


@pytest.mark.parametrize(
    "exception",
    [HomeConnectRequestError(), EventStreamInterruptedError()],
)
@patch(
    "homeassistant.components.home_connect.coordinator.EVENT_STREAM_RECONNECT_DELAY", 0
)
async def test_event_listener_resilience(
    exception: HomeConnectError,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test that the event listener is resilient to interruptions."""
    client.stream_all_events = MagicMock(
        side_effect=[exception, client.stream_all_events()]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    await hass.async_block_till_done()

    assert client.stream_all_events.call_count == 2
    assert config_entry.state == ConfigEntryState.LOADED
    assert len(config_entry._background_tasks) == 1

    event_key = EventKey.BSH_COMMON_STATUS_DOOR_STATE
    listener = AsyncMock()
    coordinator = cast(HomeConnectConfigEntry, config_entry).runtime_data
    coordinator.async_add_listener(listener, (appliance_ha_id, event_key))

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            event_key,
                            0,
                            "",
                            "",
                            "some value",
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()
    listener.assert_called_once()
