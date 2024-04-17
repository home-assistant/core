"""Tests for the Roku select platform."""

from unittest.mock import MagicMock

import pytest
from rokuecp import (
    Application,
    Device as RokuDevice,
    RokuConnectionError,
    RokuConnectionTimeoutError,
    RokuError,
)

from homeassistant.components.roku.const import DOMAIN
from homeassistant.components.roku.coordinator import SCAN_INTERVAL
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_application_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the creation and values of the Roku selects."""
    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        "1GU48T017973_application",
        suggested_object_id="my_roku_3_application",
        disabled_by=None,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_roku_3_application")
    assert state
    assert state.attributes.get(ATTR_OPTIONS) == [
        "Home",
        "Amazon Video on Demand",
        "Free FrameChannel Service",
        "MLB.TV" + "\u00ae",
        "Mediafly",
        "Netflix",
        "Pandora",
        "Pluto TV - It's Free TV",
        "Roku Channel Store",
    ]
    assert state.state == "Home"

    entry = entity_registry.async_get("select.my_roku_3_application")
    assert entry
    assert entry.unique_id == "1GU48T017973_application"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_roku_3_application",
            ATTR_OPTION: "Netflix",
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with("12")
    mock_device.app = mock_device.apps[1]

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_roku_3_application")
    assert state

    assert state.state == "Netflix"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_roku_3_application",
            ATTR_OPTION: "Home",
        },
        blocking=True,
    )

    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("home")
    mock_device.app = Application(
        app_id=None, name="Roku", version=None, screensaver=None
    )
    async_fire_time_changed(hass, dt_util.utcnow() + (SCAN_INTERVAL * 2))
    await hass.async_block_till_done()

    state = hass.states.get("select.my_roku_3_application")
    assert state
    assert state.state == "Home"


@pytest.mark.parametrize(
    ("error", "error_string"),
    [
        (RokuConnectionError, "Error communicating with Roku API"),
        (RokuConnectionTimeoutError, "Timeout communicating with Roku API"),
        (RokuError, "Invalid response from Roku API"),
    ],
)
async def test_application_select_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roku: MagicMock,
    error: RokuError,
    error_string: str,
) -> None:
    """Test error handling of the Roku selects."""
    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        "1GU48T017973_application",
        suggested_object_id="my_roku_3_application",
        disabled_by=None,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_roku.launch.side_effect = error

    with pytest.raises(HomeAssistantError, match=error_string):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.my_roku_3_application",
                ATTR_OPTION: "Netflix",
            },
            blocking=True,
        )

    state = hass.states.get("select.my_roku_3_application")
    assert state
    assert state.state == "Home"
    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with("12")


@pytest.mark.parametrize("mock_device", ["roku/rokutv-7820x.json"], indirect=True)
async def test_channel_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the creation and values of the Roku selects."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("select.58_onn_roku_tv_channel")
    assert state
    assert state.attributes.get(ATTR_OPTIONS) == [
        "99.1",
        "QVC (1.3)",
        "WhatsOn (1.1)",
        "getTV (14.3)",
    ]
    assert state.state == "getTV (14.3)"

    entry = entity_registry.async_get("select.58_onn_roku_tv_channel")
    assert entry
    assert entry.unique_id == "YN00H5555555_channel"

    # channel name
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
            ATTR_OPTION: "WhatsOn (1.1)",
        },
        blocking=True,
    )

    assert mock_roku.tune.call_count == 1
    mock_roku.tune.assert_called_with("1.1")
    mock_device.channel = mock_device.channels[0]

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.58_onn_roku_tv_channel")
    assert state
    assert state.state == "WhatsOn (1.1)"

    # channel number
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
            ATTR_OPTION: "99.1",
        },
        blocking=True,
    )

    assert mock_roku.tune.call_count == 2
    mock_roku.tune.assert_called_with("99.1")
    mock_device.channel = mock_device.channels[3]

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.58_onn_roku_tv_channel")
    assert state
    assert state.state == "99.1"


@pytest.mark.parametrize("mock_device", ["roku/rokutv-7820x.json"], indirect=True)
async def test_channel_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test error handling of the Roku selects."""
    mock_roku.tune.side_effect = RokuError

    with pytest.raises(HomeAssistantError, match="Invalid response from Roku API"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.58_onn_roku_tv_channel",
                ATTR_OPTION: "99.1",
            },
            blocking=True,
        )

    state = hass.states.get("select.58_onn_roku_tv_channel")
    assert state
    assert state.state == "getTV (14.3)"
    assert mock_roku.tune.call_count == 1
    mock_roku.tune.assert_called_with("99.1")
