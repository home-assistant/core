"""Test account and friend device registration ordering."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.vrchat.const import DOMAIN
from homeassistant.components.vrchat.coordinator import VRChatAccountDataCoordinator
from homeassistant.components.vrchat.entity import VRChatUserDataEntity
from homeassistant.components.vrchat.store import (
    InitialCurrentUserData,
    VRChatAuthCookieStore,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_init import (
    CURRENT_USER,
    CURRENT_USER_ID,
    FRIEND_USER,
    FRIEND_USER_ID,
    MockWebSocket,
)


@pytest.fixture
async def registration_entry(hass: HomeAssistant) -> AsyncGenerator[MockConfigEntry]:
    """Prepare an account and friend without connecting to VRChat."""
    InitialCurrentUserData.clear()
    VRChatAuthCookieStore.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user", CONF_PASSWORD: "password"},
        unique_id=CURRENT_USER_ID,
    )
    entry.add_to_hass(hass)
    InitialCurrentUserData[CURRENT_USER_ID] = CURRENT_USER.copy()
    with (
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.ws_connect",
            new=AsyncMock(return_value=MockWebSocket()),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_friends",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.vrchat.coordinator.VRChatAPI.get_user",
            new=AsyncMock(return_value=FRIEND_USER.copy()),
        ),
    ):
        yield entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    InitialCurrentUserData.clear()
    VRChatAuthCookieStore.clear()


async def test_only_account_device_exists_during_friend_construction(
    hass: HomeAssistant,
    registration_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Resolve the parent before entity adds while leaving friends to the framework."""
    original_init = VRChatUserDataEntity.__init__
    constructed_friends: list[VRChatUserDataEntity] = []

    def check_constructor(
        entity: VRChatUserDataEntity,
        coordinator: VRChatAccountDataCoordinator,
        user_id: str,
    ) -> None:
        if user_id == FRIEND_USER_ID:
            assert not er.async_entries_for_config_entry(
                entity_registry, registration_entry.entry_id
            )
            assert (
                device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{CURRENT_USER_ID}:{CURRENT_USER_ID}"),
                    registration_entry.entry_id,
                )
                is not None
            )
            assert (
                device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"),
                    registration_entry.entry_id,
                )
                is None
            )
            constructed_friends.append(entity)
        original_init(entity, coordinator, user_id)

    with patch.object(VRChatUserDataEntity, "__init__", check_constructor):
        assert await hass.config_entries.async_setup(registration_entry.entry_id)
        await hass.async_block_till_done()

    assert len(constructed_friends) == 4
    assert len(hass.states.async_entity_ids("sensor")) == 8
    account = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{CURRENT_USER_ID}:{CURRENT_USER_ID}"), registration_entry.entry_id
    )
    friend = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), registration_entry.entry_id
    )
    assert account is not None
    assert friend is not None
    assert friend.via_device_id == account.id
    assert friend.name == FRIEND_USER["displayName"]
    assert len(device_registry.devices) == 2


async def test_friend_registration_does_not_wait_for_account_entities(
    hass: HomeAssistant,
    registration_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Account entity preparation cannot delay friends or break their parent link."""
    release_account = asyncio.Event()
    friend_added = asyncio.Event()
    original_prepare = VRChatUserDataEntity.async_prepare_to_add_to_hass
    original_added = VRChatUserDataEntity.async_added_to_hass

    async def delayed_account_prepare(entity: VRChatUserDataEntity) -> None:
        if entity.user_id == CURRENT_USER_ID:
            await release_account.wait()
        await original_prepare(entity)

    async def signal_friend_added(entity: VRChatUserDataEntity) -> None:
        await original_added(entity)
        if entity.user_id == FRIEND_USER_ID:
            friend_added.set()

    with (
        patch.object(
            VRChatUserDataEntity,
            "async_prepare_to_add_to_hass",
            delayed_account_prepare,
        ),
        patch.object(VRChatUserDataEntity, "async_added_to_hass", signal_friend_added),
    ):
        setup = hass.async_create_task(
            hass.config_entries.async_setup(registration_entry.entry_id)
        )
        try:
            async with asyncio.timeout(10):
                await friend_added.wait()
            assert not release_account.is_set()
            assert (
                entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, f"status.{CURRENT_USER_ID}:{CURRENT_USER_ID}"
                )
                is None
            )
            account = device_registry.async_get_device_by_identifier(
                (DOMAIN, f"{CURRENT_USER_ID}:{CURRENT_USER_ID}"),
                registration_entry.entry_id,
            )
            friend = device_registry.async_get_device_by_identifier(
                (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"),
                registration_entry.entry_id,
            )
            assert account is not None
            assert friend is not None
            assert friend.via_device_id == account.id
            assert friend.name == FRIEND_USER["displayName"]
        finally:
            release_account.set()
            assert await setup
            await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("sensor")) == 8


async def test_framework_cannot_supply_parent_during_friend_construction(
    hass: HomeAssistant,
    registration_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent entity adds alone cannot satisfy constructor-time parent lookup."""
    with patch.object(VRChatAccountDataCoordinator, "async_register_account_device"):
        assert await hass.config_entries.async_setup(registration_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        "ValueError: There is no device with identifier "
        f"('vrchat', '{CURRENT_USER_ID}:{CURRENT_USER_ID}')"
    ) in caplog.text
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{CURRENT_USER_ID}:{FRIEND_USER_ID}"), registration_entry.entry_id
        )
        is None
    )
    # Account adds run later, despite the platform failing to construct friends.
    assert len(hass.states.async_entity_ids("sensor")) == 4
