"""Test the Matrix bot selection logic (_get_matrix_bot in services.py)."""

from unittest.mock import patch

import pytest

from homeassistant.components.matrix import DOMAIN, MatrixBot
from homeassistant.components.matrix.const import (
    CONF_CONFIG_ENTRY_ID,
    CONF_HOMESERVER,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import (
    TEST_MXID,
    TEST_PASSWORD,
    TEST_ROOM_A_ID,
    TEST_ROOM_B_ID,
    TEST_ROOM_C_ID,
    _MockAsyncClient,
)

from tests.common import MockConfigEntry

TEST_MXID_2 = "@user2:example.com"

_ENTRY_1_DATA = {
    CONF_HOMESERVER: "https://matrix.example.com",
    CONF_USERNAME: TEST_MXID,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_VERIFY_SSL: True,
    "rooms": [TEST_ROOM_A_ID, TEST_ROOM_B_ID],
}

# Entry 2 shares TEST_ROOM_B_ID with Entry 1 (to test ambiguous room matching)
# and has TEST_ROOM_C_ID unique to it (to test unambiguous room matching)
_ENTRY_2_DATA = {
    CONF_HOMESERVER: "https://matrix.example.com",
    CONF_USERNAME: TEST_MXID_2,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_VERIFY_SSL: True,
    "rooms": [TEST_ROOM_B_ID, TEST_ROOM_C_ID],
}


@pytest.fixture
async def two_matrix_bots(
    hass: HomeAssistant,
    mock_save_json,
    mock_allowed_path,
) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Set up two Matrix config entries with non-overlapping and overlapping rooms."""
    with patch("homeassistant.components.matrix.AsyncClient", _MockAsyncClient):
        await async_setup_component(hass, DOMAIN, {})

        entry1 = MockConfigEntry(
            domain=DOMAIN,
            data=_ENTRY_1_DATA,
            unique_id=TEST_MXID,
            title=TEST_MXID,
        )
        entry2 = MockConfigEntry(
            domain=DOMAIN,
            data=_ENTRY_2_DATA,
            unique_id=TEST_MXID_2,
            title=TEST_MXID_2,
        )
        entry1.add_to_hass(hass)
        entry2.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry1.entry_id)
        assert await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        await hass.async_start()
        await hass.async_block_till_done()

        assert isinstance(entry1.runtime_data, MatrixBot)
        assert isinstance(entry2.runtime_data, MatrixBot)

    return entry1, entry2


async def test_no_loaded_entries_raises(hass: HomeAssistant) -> None:
    """ServiceValidationError when no Matrix entries are loaded."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hi", ATTR_TARGET: [TEST_ROOM_A_ID]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_config_entries_loaded"


async def test_multiple_entries_no_target_raises(
    hass: HomeAssistant,
    two_matrix_bots: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """ServiceValidationError when multiple entries are loaded with no disambiguating rooms."""
    entry1, entry2 = two_matrix_bots
    bot1: MatrixBot = entry1.runtime_data
    bot2: MatrixBot = entry2.runtime_data
    await bot1._login()
    await bot2._login()

    # No config_entry_id, and target room matches BOTH bots → ambiguous
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hi", ATTR_TARGET: [TEST_ROOM_B_ID]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "multiple_entries_match"


async def test_multiple_entries_no_room_match_raises(
    hass: HomeAssistant,
    two_matrix_bots: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """ServiceValidationError when multiple entries are loaded and no room matches any bot."""
    entry1, entry2 = two_matrix_bots
    bot1: MatrixBot = entry1.runtime_data
    bot2: MatrixBot = entry2.runtime_data
    await bot1._login()
    await bot2._login()

    # No config_entry_id and target room belongs to neither bot
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hi", ATTR_TARGET: ["!unknown:example.com"]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "multiple_entries_loaded"


async def test_explicit_config_entry_id_selects_correct_bot(
    hass: HomeAssistant,
    two_matrix_bots: tuple[MockConfigEntry, MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit config_entry_id routes to the correct bot."""
    entry1, _entry2 = two_matrix_bots
    await entry1.runtime_data._login()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "hi",
            ATTR_TARGET: [TEST_ROOM_A_ID],
            CONF_CONFIG_ENTRY_ID: entry1.entry_id,
        },
        blocking=True,
    )

    assert f"Message delivered to room '{TEST_ROOM_A_ID}'" in caplog.messages


async def test_explicit_config_entry_id_not_found_raises(
    hass: HomeAssistant,
    two_matrix_bots: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """ServiceValidationError when config_entry_id does not match any loaded entry."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_MESSAGE: "hi",
                ATTR_TARGET: [TEST_ROOM_A_ID],
                CONF_CONFIG_ENTRY_ID: "nonexistent_entry_id",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "config_entry_not_found"


async def test_target_room_disambiguates_to_one_bot(
    hass: HomeAssistant,
    two_matrix_bots: tuple[MockConfigEntry, MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Target room unique to one bot selects that bot without config_entry_id."""
    entry1, _entry2 = two_matrix_bots
    await entry1.runtime_data._login()

    # TEST_ROOM_A_ID is only in entry1's rooms
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "hi", ATTR_TARGET: [TEST_ROOM_A_ID]},
        blocking=True,
    )

    assert f"Message delivered to room '{TEST_ROOM_A_ID}'" in caplog.messages
