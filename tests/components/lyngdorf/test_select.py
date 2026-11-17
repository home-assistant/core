"""Tests for the Lyngdorf select platform."""

from unittest.mock import MagicMock, patch

from lyngdorf import LyngdorfInvalidValueError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import _selector, notify_receiver_update


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the select platform."""
    return [Platform.SELECT]


ROOM_PERFECT_ENTITY_ID = "select.mock_lyngdorf_roomperfect_position"
VOICING_ENTITY_ID = "select.mock_lyngdorf_voicing"


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_room_perfect_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a RoomPerfect position."""
    mock_receiver.room_perfect_position_selector = _selector(
        "focus", ["focus", "global"]
    )

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: ROOM_PERFECT_ENTITY_ID,
            SelectServiceArgument.OPTION: "global",
        },
        blocking=True,
    )

    mock_receiver.room_perfect_position_selector.select.assert_called_once_with(
        "global"
    )


async def test_select_option_awaits_an_awaitable_setter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a setter that returns a coroutine is awaited rather than dropped."""
    mock_receiver.voicing_selector = _selector("Neutral", ["Neutral", "Music", "Movie"])
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: VOICING_ENTITY_ID,
            SelectServiceArgument.OPTION: "Music",
        },
        blocking=True,
    )

    mock_receiver.voicing_selector.select.assert_awaited_once_with("Music")


async def test_voicing_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a voicing."""
    mock_receiver.voicing_selector = _selector("Neutral", ["Neutral", "Music", "Movie"])

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: VOICING_ENTITY_ID,
            SelectServiceArgument.OPTION: "Movie",
        },
        blocking=True,
    )

    mock_receiver.voicing_selector.select.assert_called_once_with("Movie")


async def test_select_invalid_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test an option the device no longer offers is reported to the user."""
    mock_receiver.voicing_selector.select.side_effect = LyngdorfInvalidValueError(
        "not valid"
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                TargetKey.ENTITY_ID: VOICING_ENTITY_ID,
                SelectServiceArgument.OPTION: "Movie",
            },
            blocking=True,
        )

    assert err.value.translation_key == "invalid_option"
    assert err.value.translation_placeholders == {
        "option": "Movie",
        "options": "Neutral, Music, Movie",
    }


@pytest.mark.parametrize(
    ("selector_attr", "entity_id", "surviving_entity_id"),
    [
        pytest.param(
            "room_perfect_position_selector",
            ROOM_PERFECT_ENTITY_ID,
            VOICING_ENTITY_ID,
            id="position",
        ),
        pytest.param(
            "voicing_selector",
            VOICING_ENTITY_ID,
            ROOM_PERFECT_ENTITY_ID,
            id="voicing",
        ),
    ],
)
async def test_select_not_created_without_selector(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    selector_attr: str,
    entity_id: str,
    surviving_entity_id: str,
) -> None:
    """Test a select is absent when the model lacks its selector."""
    setattr(mock_receiver, selector_attr, None)
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.lyngdorf.PLATFORMS", [Platform.SELECT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
    assert entity_registry.async_get(surviving_entity_id) is not None
    assert "Error adding entity" not in caplog.text
