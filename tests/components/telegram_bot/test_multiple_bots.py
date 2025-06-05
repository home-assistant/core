"""Test automatic config entry selection for multiple telegram bots."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.telegram_bot import DOMAIN, SERVICE_SEND_MESSAGE
from homeassistant.components.telegram_bot.const import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    CONF_CHAT_ID,
    CONF_CONFIG_ENTRY_ID,
    PLATFORM_BROADCAST,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_first_runtime_service() -> AsyncMock:
    """Mock runtime service for first telegram bot."""
    service = AsyncMock()

    # Chat IDs that belong to this bot
    bot_chat_ids = {111111111, 222222222}

    async def mock_send_message(target=None, **kwargs):
        if target is None:
            return {111111111: 12345}  # Default first chat
        if isinstance(target, int):
            target = [target]
        # Only return chat IDs that belong to this bot AND are in target
        return {chat_id: 12345 for chat_id in target if chat_id in bot_chat_ids}

    service.send_message = AsyncMock(side_effect=mock_send_message)
    service.send_file = AsyncMock(side_effect=mock_send_message)
    service.send_sticker = AsyncMock(side_effect=mock_send_message)
    service.send_location = AsyncMock(side_effect=mock_send_message)
    service.send_poll = AsyncMock(side_effect=mock_send_message)
    service.answer_callback_query = AsyncMock()
    service.delete_message = AsyncMock()
    service.edit_message = AsyncMock()
    return service


@pytest.fixture
def mock_second_runtime_service() -> AsyncMock:
    """Mock runtime service for second telegram bot."""
    service = AsyncMock()

    # Chat IDs that belong to this bot
    bot_chat_ids = {333333333, 444444444}

    async def mock_send_message(target=None, **kwargs):
        if target is None:
            return {333333333: 12345}  # Default first chat
        if isinstance(target, int):
            target = [target]
        # Only return chat IDs that belong to this bot AND are in target
        return {chat_id: 12345 for chat_id in target if chat_id in bot_chat_ids}

    service.send_message = AsyncMock(side_effect=mock_send_message)
    service.send_file = AsyncMock(side_effect=mock_send_message)
    service.send_sticker = AsyncMock(side_effect=mock_send_message)
    service.send_location = AsyncMock(side_effect=mock_send_message)
    service.send_poll = AsyncMock(side_effect=mock_send_message)
    service.answer_callback_query = AsyncMock()
    service.delete_message = AsyncMock()
    service.edit_message = AsyncMock()
    return service


@pytest.fixture
def mock_first_bot_config_entry(mock_first_runtime_service: AsyncMock) -> MockConfigEntry:
    """Return the first mocked config entry."""
    entry = MockConfigEntry(
        unique_id="first_bot_api_key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "first_bot_api_key",
        },
        options={"parse_mode": "markdown"},
        subentries_data=[
            ConfigSubentryData(
                unique_id="111111111",
                data={CONF_CHAT_ID: 111111111},
                subentry_id="first_chat_id",
                subentry_type="allowed_chat_ids",
                title="First Bot Chat",
            ),
            ConfigSubentryData(
                unique_id="222222222",
                data={CONF_CHAT_ID: 222222222},
                subentry_id="second_chat_id",
                subentry_type="allowed_chat_ids",
                title="First Bot Second Chat",
            ),
        ],
    )
    entry.runtime_data = mock_first_runtime_service
    return entry


@pytest.fixture
def mock_second_bot_config_entry(mock_second_runtime_service: AsyncMock) -> MockConfigEntry:
    """Return the second mocked config entry."""
    entry = MockConfigEntry(
        unique_id="second_bot_api_key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "second_bot_api_key",
        },
        options={"parse_mode": "markdown"},
        subentries_data=[
            ConfigSubentryData(
                unique_id="333333333",
                data={CONF_CHAT_ID: 333333333},
                subentry_id="third_chat_id",
                subentry_type="allowed_chat_ids",
                title="Second Bot Chat",
            ),
            ConfigSubentryData(
                unique_id="444444444",
                data={CONF_CHAT_ID: 444444444},
                subentry_id="fourth_chat_id",
                subentry_type="allowed_chat_ids",
                title="Second Bot Second Chat",
            ),
        ],
    )
    entry.runtime_data = mock_second_runtime_service
    return entry


async def test_automatic_config_entry_selection_by_target(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test that correct config entry is selected based on target chat_id."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending to first bot's chat - should use first config entry
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for first bot",
            ATTR_TARGET: 111111111,  # This chat_id belongs to first bot
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345
    assert response["chats"][0]["chat_id"] == 111111111

    # Test sending to second bot's chat - should use second config entry
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for second bot",
            ATTR_TARGET: 333333333,  # This chat_id belongs to second bot
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345
    assert response["chats"][0]["chat_id"] == 333333333


async def test_automatic_config_entry_selection_multiple_targets(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test config entry selection with multiple targets from same bot."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending to multiple chats from first bot
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for first bot multiple chats",
            ATTR_TARGET: [111111111, 222222222],  # Both belong to first bot
        },
        blocking=True,
        return_response=True,
    )

    assert len(response["chats"]) == 2
    chat_ids = [chat["chat_id"] for chat in response["chats"]]
    assert 111111111 in chat_ids
    assert 222222222 in chat_ids


async def test_no_matching_config_entry_for_target(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test error when target chat_id doesn't match any config entry."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending to unknown chat_id - should raise error
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_MESSAGE: "test message for unknown chat",
                ATTR_TARGET: 999999999,  # This chat_id doesn't belong to any bot
            },
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "no_matching_target"


async def test_mixed_targets_from_different_bots(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test behavior with targets from different bots - should use first matching bot."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending to targets from both bots - should use first matching config entry
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for mixed targets",
            ATTR_TARGET: [111111111, 333333333],  # First from bot1, second from bot2
        },
        blocking=True,
        return_response=True,
    )

    # Should only send to the chat that belongs to the selected config entry (first bot)
    assert len(response["chats"]) == 1
    assert response["chats"][0]["chat_id"] == 111111111


async def test_single_target_as_int(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test that single target as int (not list) works correctly."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending to single target as int
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for single target",
            ATTR_TARGET: 333333333,  # Single int, not list
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345
    assert response["chats"][0]["chat_id"] == 333333333


async def test_fallback_to_original_behavior_without_target(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test that without target, original error behavior is preserved."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending without target - should raise multiple config entry error
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_MESSAGE: "test message without target",
                # No ATTR_TARGET specified
            },
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "multiple_config_entry"


async def test_explicit_config_entry_id(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_second_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test using explicit config entry ID to select bot."""
    # Setup component and both config entries
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    mock_second_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending with explicit config entry ID
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            CONF_CONFIG_ENTRY_ID: mock_second_bot_config_entry.entry_id,
            ATTR_MESSAGE: "test message with explicit config entry",
            ATTR_TARGET: 333333333,
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345
    assert response["chats"][0]["chat_id"] == 333333333


async def test_single_config_entry_behavior(
    hass: HomeAssistant,
    mock_first_bot_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test that single config entry works without requiring target."""
    # Setup component and only one config entry
    await async_setup_component(hass, DOMAIN, {})
    mock_first_bot_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    # Test sending without target - should work with single config entry
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "test message for single config entry",
            ATTR_TARGET: 111111111,
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345
    assert response["chats"][0]["chat_id"] == 111111111
