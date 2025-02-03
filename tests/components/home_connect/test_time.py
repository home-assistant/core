"""Tests for home_connect time entities."""

from collections.abc import Awaitable, Callable
from datetime import time
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfSettings,
    EventMessage,
    EventType,
    GetSetting,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectApiError, HomeConnectError
import pytest

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TIME]


async def test_time(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test time entity."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance_ha_id", ["Oven"], indirect=True)
async def test_paired_depaired_devices_flow(
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize("appliance_ha_id", ["Oven"], indirect=True)
async def test_connected_devices(
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_settings_original_mock = client.get_settings

    async def get_settings_side_effect(ha_id: str):
        if ha_id == appliance_ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_settings_original_mock.side_effect(ha_id)

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    new_entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert len(new_entity_entries) > len(entity_entries)


@pytest.mark.parametrize("appliance_ha_id", ["Oven"], indirect=True)
async def test_time_entity_availabilty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test if time entities availability are based on the appliance connection state."""
    entity_ids = [
        "time.oven_alarm_clock",
    ]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
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
                appliance_ha_id,
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


@pytest.mark.parametrize("appliance_ha_id", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            SettingKey.BSH_COMMON_ALARM_CLOCK,
        ),
    ],
)
async def test_time_entity_functionality(
    appliance_ha_id: str,
    entity_id: str,
    setting_key: SettingKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test time entity functionality."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    value = 30
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state != value
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(second=value),
        },
    )
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance_ha_id, setting_key=setting_key, value=value
    )
    assert hass.states.is_state(entity_id, str(time(second=value)))


@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            SettingKey.BSH_COMMON_ALARM_CLOCK,
            "set_setting",
        ),
    ],
)
async def test_time_entity_error(
    entity_id: str,
    setting_key: SettingKey,
    mock_attr: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test time entity error."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=setting_key,
                raw_key=setting_key.value,
                value=30,
            )
        ]
    )
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeConnectError):
        await getattr(client_with_exception, mock_attr)()

    with pytest.raises(
        HomeAssistantError, match=r"Error.*assign.*value.*to.*setting.*"
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TIME: time(minute=1),
            },
            blocking=True,
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2
