"""Tests for WiiM audio output selection."""

from datetime import timedelta
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
from homeassistant.util import dt as dt_util

from . import fire_general_update, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "select.test_wiim_device_audio_output"
OPTIONS = ["Line Out", "Optical Out", "Other Out"]

pytestmark = pytest.mark.usefixtures("mock_wiim_controller", "mock_audio_output")


@pytest.fixture
def mock_audio_output(mock_wiim_device: AsyncMock) -> None:
    """Configure the SDK boundary for audio output tests."""
    mock_wiim_device.supports_http_api = True
    mock_wiim_device.supported_output_modes = tuple(OPTIONS)
    mock_wiim_device.output_mode = "Line Out"
    mock_wiim_device.async_refresh_audio_capabilities = AsyncMock()
    mock_wiim_device.get_audio_output_hw_mode.return_value = "Line Out"

    async def set_output_mode(option: str) -> None:
        mock_wiim_device.output_mode = option
        mock_wiim_device.get_audio_output_hw_mode.return_value = option

    mock_wiim_device.async_set_output_mode = AsyncMock(side_effect=set_output_mode)


@pytest.mark.parametrize("current", ["Line Out", "Other Out"])
async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    entity_registry: er.EntityRegistry,
    current: str,
) -> None:
    """Initialize the selector from device capabilities and active output."""
    mock_wiim_device.output_mode = current
    mock_wiim_device.get_audio_output_hw_mode.return_value = current
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == (STATE_UNKNOWN if current == "Other Out" else current)
    assert state.attributes[ATTR_OPTIONS] == ["Line Out", "Optical Out"]
    registry_entry = entity_registry.async_get(ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is EntityCategory.CONFIG
    mock_wiim_device.async_refresh_audio_capabilities.assert_awaited_once_with()
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
    mock_wiim_device.async_refresh_audio_capabilities.assert_not_awaited()


@pytest.mark.parametrize(
    "method_name",
    ["async_refresh_audio_capabilities", "get_audio_output_hw_mode"],
)
@pytest.mark.parametrize(
    "error",
    [
        WiimRequestException("failed"),
        UpnpError("failed"),
        aiohttp.ClientError("failed"),
        TimeoutError(),
    ],
)
async def test_initial_read_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    method_name: str,
    error: Exception,
) -> None:
    """Retry platform setup after a transient initial output read failure."""
    await hass.async_start()
    method = getattr(mock_wiim_device, method_name)
    method.side_effect = error
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID) is None
    method.assert_awaited_once_with()

    method.side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Line Out"
    assert method.await_count == 2


@pytest.mark.parametrize("option", ["Optical Out", "Other Out"])
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    option: str,
) -> None:
    """Select a known output or reject an unsupported option at the platform boundary."""
    await setup_integration(hass, mock_config_entry)
    if option == "Other Out":
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
                blocking=True,
            )
        mock_wiim_device.async_set_output_mode.assert_not_awaited()
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == "Line Out"
        return

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    mock_wiim_device.async_set_output_mode.assert_awaited_once_with(option)
    assert state.state == option


async def test_select_cycle_and_last(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Cycle through selectable outputs and select the last real output."""
    await setup_integration(hass, mock_config_entry)
    for service, expected in (
        (SERVICE_SELECT_NEXT, "Optical Out"),
        (SERVICE_SELECT_NEXT, "Line Out"),
        (SERVICE_SELECT_LAST, "Optical Out"),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                **({ATTR_CYCLE: True} if service == SERVICE_SELECT_NEXT else {}),
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
    ("options", "current", "expected"),
    [
        (OPTIONS, "Optical Out", "Optical Out"),
        (OPTIONS, "Other Out", STATE_UNKNOWN),
        (OPTIONS, "Unknown output", STATE_UNKNOWN),
        (["USB Out", "Other Out"], "USB Out", "USB Out"),
        ([], None, STATE_UNAVAILABLE),
        (["Other Out"], "Other Out", STATE_UNAVAILABLE),
    ],
)
async def test_output_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    options: list[str],
    current: str | None,
    expected: str,
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
    assert state.attributes[ATTR_OPTIONS] == [
        option for option in options if option != "Other Out"
    ]
    mock_wiim_device.async_refresh_audio_capabilities.assert_awaited_once_with()
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
