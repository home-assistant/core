"""Tests for WiiM audio output selection."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
from async_upnp_client.exceptions import UpnpError
import pytest
from wiim.exceptions import WiimRequestException

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import fire_general_update, setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "select.test_wiim_device"
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
    mock_wiim_device.async_set_output_mode = AsyncMock()


async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Initialize the selector from device capabilities and active output."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Line Out"
    assert state.attributes[ATTR_OPTIONS] == OPTIONS
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


@pytest.mark.parametrize("option", ["Optical Out", "Other Out"])
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    option: str,
) -> None:
    """Select a known output; Other Out is a display-only option."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    if option == "Other Out":
        mock_wiim_device.async_set_output_mode.assert_not_awaited()
        assert state.state == "Line Out"
    else:
        mock_wiim_device.async_set_output_mode.assert_awaited_once_with(option)
        assert state.state == option


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
        (OPTIONS, "Other Out", "Other Out"),
        (OPTIONS, "Unknown output", STATE_UNKNOWN),
        (["USB Out", "Other Out"], "USB Out", "USB Out"),
        ([], None, STATE_UNAVAILABLE),
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
    assert state.attributes[ATTR_OPTIONS] == options
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
