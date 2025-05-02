"""Tests for home_connect binary_sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    StatusKey,
)
from aiohomeconnect.model.error import HomeConnectApiError
import pytest

from homeassistant.components.home_connect.const import (
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


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
    assert config_entry.state == ConfigEntryState.LOADED

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
            (StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,),
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
    get_status_original_mock = client.get_status

    def get_status_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return get_status_original_mock.return_value

    client.get_status = AsyncMock(side_effect=get_status_side_effect)
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_status = get_status_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    assert entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{appliance.ha_id}-{EventKey.BSH_COMMON_APPLIANCE_CONNECTED}",
    )
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
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

    for key in (*keys_to_check, EventKey.BSH_COMMON_APPLIANCE_CONNECTED):
        assert entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_binary_sensors_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if binary sensor entities availability are based on the appliance connection state."""
    entity_ids = [
        "binary_sensor.washer_remote_control",
    ]
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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


@pytest.mark.parametrize(
    ("entity_id", "event_key", "event_value_update", "expected", "appliance"),
    [
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            False,
            STATE_OFF,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            True,
            STATE_ON,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            "",
            STATE_UNKNOWN,
            "Washer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_CLOSED,
            STATE_OFF,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_OPEN,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            "",
            STATE_UNKNOWN,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
async def test_binary_sensors_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    event_key: EventKey,
    event_value_update: str,
    appliance: HomeAppliance,
    expected: str,
) -> None:
    """Tests for Home Connect Fridge appliance door states."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=event_value_update,
                        )
                    ],
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_connected_sensor_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if the connected binary sensor reports the right values."""
    entity_id = "binary_sensor.washer_connectivity"
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, STATE_ON)

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

    assert hass.states.is_state(entity_id, STATE_OFF)

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

    assert hass.states.is_state(entity_id, STATE_ON)
