"""Tests for the Besen select platform."""

from unittest.mock import AsyncMock, Mock

from besen.exceptions import CommandFailed
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import publish_besen_state
from .conftest import charger_state, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

LANGUAGE_ENTITY_ID = "select.garage_language"
TEMPERATURE_UNIT_ENTITY_ID = "select.garage_temperature_unit"


async def test_select_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test select entity states and registry data."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_besen_client.async_start.assert_awaited_once()


async def test_select_updates_from_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test select states update from client push data."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    publish_besen_state(
        mock_besen_client,
        charger_state(language="Deutsch", temperature_unit="Fahrenheit"),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(LANGUAGE_ENTITY_ID)) is not None
    assert state.state == "german"
    assert (state := hass.states.get(TEMPERATURE_UNIT_ENTITY_ID)) is not None
    assert state.state == "fahrenheit"


@pytest.mark.parametrize(
    ("available", "authenticated"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_select_unavailable_from_client_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    available: bool,
    authenticated: bool,
) -> None:
    """Test select availability follows client state."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    publish_besen_state(
        mock_besen_client,
        charger_state(available=available, authenticated=authenticated),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(LANGUAGE_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_select_unknown_for_unreported_or_unsupported_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test unreported and unsupported values are unknown."""

    mock_besen_client.state = charger_state(
        language="Klingon",
        temperature_unit=None,
    )

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    assert (state := hass.states.get(LANGUAGE_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get(TEMPERATURE_UNIT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "option", "method", "wire_value"),
    [
        (LANGUAGE_ENTITY_ID, "english", "async_set_language", "English"),
        (LANGUAGE_ENTITY_ID, "italian", "async_set_language", "Italiano"),
        (LANGUAGE_ENTITY_ID, "german", "async_set_language", "Deutsch"),
        (LANGUAGE_ENTITY_ID, "french", "async_set_language", "Fran\u00e7ais"),
        (LANGUAGE_ENTITY_ID, "spanish", "async_set_language", "Espa\u00f1ol"),
        (
            LANGUAGE_ENTITY_ID,
            "hebrew",
            "async_set_language",
            "\u05e2\u05d1\u05e8\u05d9\u05ea",
        ),
        (LANGUAGE_ENTITY_ID, "polish", "async_set_language", "Polski"),
        (LANGUAGE_ENTITY_ID, "chinese", "async_set_language", "\u4e2d\u6587"),
        (
            TEMPERATURE_UNIT_ENTITY_ID,
            "celsius",
            "async_set_temperature_unit",
            "Celsius",
        ),
        (
            TEMPERATURE_UNIT_ENTITY_ID,
            "fahrenheit",
            "async_set_temperature_unit",
            "Fahrenheit",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    entity_id: str,
    option: str,
    method: str,
    wire_value: str,
) -> None:
    """Test selecting an option sends its protocol value and updates state."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    await hass.async_block_till_done()

    getattr(mock_besen_client, method).assert_awaited_once_with(wire_value)
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == option


async def test_select_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test select command failures are translated."""

    mock_besen_client.async_set_language = AsyncMock(
        side_effect=CommandFailed("failed")
    )

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: LANGUAGE_ENTITY_ID, ATTR_OPTION: "german"},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
    assert (state := hass.states.get(LANGUAGE_ENTITY_ID)) is not None
    assert state.state == "english"
