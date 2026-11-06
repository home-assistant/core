"""Tests for WiiM audio output selection."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
from async_upnp_client.exceptions import UpnpError
import pytest
from wiim.exceptions import WiimRequestException

from homeassistant.components.select import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.wiim.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import MockConfigEntry, fire_general_update, setup_integration

ENTITY_ID = "select.test_wiim_device_audio_output"
OPTIONS = ["Line Out", "Optical Out", "Other Out"]

pytestmark = pytest.mark.usefixtures("mock_wiim_controller", "mock_audio_output")


@pytest.fixture
def mock_audio_output(mock_wiim_device: AsyncMock) -> None:
    """Configure the SDK boundary for audio output tests."""
    mock_wiim_device.supports_http_api = True
    mock_wiim_device.supported_output_modes = tuple(OPTIONS)
    mock_wiim_device.output_mode = "Line Out"
    mock_wiim_device.get_audio_output_hw_mode.return_value = "Line Out"

    async def set_output_mode(option: str) -> None:
        mock_wiim_device.output_mode = option
        mock_wiim_device.get_audio_output_hw_mode.return_value = option

    mock_wiim_device.async_set_output_mode = AsyncMock(side_effect=set_output_mode)


@pytest.mark.parametrize(
    ("fallback", "current", "expected"),
    [
        ("Other Out", "Line Out", "Line Out"),
        ("Other Out", "Other Out", STATE_UNKNOWN),
        ("other_out", "other_out", STATE_UNKNOWN),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    entity_registry: er.EntityRegistry,
    fallback: str,
    current: str,
    expected: str,
) -> None:
    """Initialize the selector from device capabilities and active output."""
    mock_wiim_device.supported_output_modes = ("Line Out", "Optical Out", fallback)
    mock_wiim_device.output_mode = current
    mock_wiim_device.get_audio_output_hw_mode.return_value = current
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes[ATTR_OPTIONS] == ["Line Out", "Optical Out"]
    registry_entry = entity_registry.async_get(ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is EntityCategory.CONFIG
    mock_wiim_device.get_audio_output_hw_mode.assert_awaited_once_with()


async def test_no_http_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Do not create a selector for devices without HTTP API support."""
    mock_wiim_device.supports_http_api = False
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize(
    "error",
    [
        WiimRequestException("failed"),
        UpnpError("failed"),
        aiohttp.ClientError("failed"),
        TimeoutError(),
    ],
)
async def test_initial_read_failure_recovers_from_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    error: Exception,
) -> None:
    """Keep the entity after a failed read and recover through a device event."""
    mock_wiim_device.output_mode = None
    mock_wiim_device.get_audio_output_hw_mode.side_effect = error
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_OPTIONS] == ["Line Out", "Optical Out"]
    mock_wiim_device.get_audio_output_hw_mode.assert_awaited_once_with()
    mock_wiim_device.output_mode = "Optical Out"
    await fire_general_update(hass, mock_wiim_device)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Optical Out"
    mock_wiim_device.get_audio_output_hw_mode.assert_awaited_once_with()


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Select a known output through the select service."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Optical Out"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    mock_wiim_device.async_set_output_mode.assert_awaited_once_with("Optical Out")
    assert state.state == "Optical Out"


async def test_non_selectable_output_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Reject the SDK fallback at the select platform's option validation."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "other_out"},
            blocking=True,
        )
    mock_wiim_device.async_set_output_mode.assert_not_awaited()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Line Out"


async def test_select_cycle_and_last(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Cycle through selectable outputs and select the last real output."""
    await setup_integration(hass, mock_config_entry)
    for service, service_data, expected in (
        (SERVICE_SELECT_NEXT, {ATTR_CYCLE: True}, "Optical Out"),
        (SERVICE_SELECT_NEXT, {ATTR_CYCLE: True}, "Line Out"),
        (SERVICE_SELECT_LAST, {}, "Optical Out"),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                **service_data,
            },
            blocking=True,
        )
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected
        mock_wiim_device.async_set_output_mode.assert_awaited_with(expected)
    assert mock_wiim_device.async_set_output_mode.await_count == 3


@pytest.mark.parametrize(
    "error",
    [
        WiimRequestException("failed"),
        UpnpError("failed"),
        aiohttp.ClientError("failed"),
        TimeoutError(),
    ],
)
async def test_select_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    error: Exception,
) -> None:
    """Report command failures without changing the selected output."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.async_set_output_mode.side_effect = error
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Optical Out"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "command_failed"
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Line Out"


@pytest.mark.parametrize(
    ("options", "current", "expected", "expected_options"),
    [
        (OPTIONS, "Optical Out", "Optical Out", ["Line Out", "Optical Out"]),
        (OPTIONS, "Other Out", STATE_UNKNOWN, ["Line Out", "Optical Out"]),
        (["Line Out", "other_out"], "other_out", STATE_UNKNOWN, ["Line Out"]),
        (OPTIONS, "Unknown output", STATE_UNKNOWN, ["Line Out", "Optical Out"]),
        (["USB Out", "Other Out"], "USB Out", "USB Out", ["USB Out"]),
        ([], None, STATE_UNAVAILABLE, []),
        (["Other Out"], "Other Out", STATE_UNAVAILABLE, []),
        (["other_out"], "other_out", STATE_UNAVAILABLE, []),
    ],
)
async def test_output_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    options: list[str],
    current: str | None,
    expected: str,
    expected_options: list[str],
) -> None:
    """Refresh through the SDK callback and real dispatcher, without HTTP reads."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.supported_output_modes = tuple(options)
    mock_wiim_device.output_mode = current
    mock_wiim_device.rendering_control_event_callback(MagicMock(), [])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes[ATTR_OPTIONS] == expected_options
    mock_wiim_device.get_audio_output_hw_mode.assert_awaited_once_with()


async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Follow device availability updates and recover with the current output."""
    await setup_integration(hass, mock_config_entry)
    for available, expected in ((False, STATE_UNAVAILABLE), (True, "Line Out")):
        mock_wiim_device.available = available
        await fire_general_update(hass, mock_wiim_device)
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected


async def test_updates_without_media_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep output updates independent of a disabled media player."""
    mock_config_entry.add_to_hass(hass)
    media_player = entity_registry.async_get_or_create(
        "media_player",
        DOMAIN,
        mock_wiim_device.udn,
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(media_player.entity_id) is None
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Line Out"

    mock_wiim_device.output_mode = "Optical Out"
    mock_wiim_device.rendering_control_event_callback(MagicMock(), [])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Optical Out"

    for available, expected in ((False, STATE_UNAVAILABLE), (True, "Optical Out")):
        mock_wiim_device.available = available
        await fire_general_update(hass, mock_wiim_device)
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected

    mock_wiim_device.ensure_subscriptions.assert_awaited_once_with()
    mock_wiim_device.get_audio_output_hw_mode.assert_awaited_once_with()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_wiim_device.general_event_callback is None
    assert mock_wiim_device.rendering_control_event_callback is None
