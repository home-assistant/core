"""Test HomeKit initialization."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    DOMAIN as DOMAIN_HOMEKIT,
    EVENT_HOMEKIT_CHANGED,
)
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .util import PATH_HOMEKIT

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_homekit_changed_event(
    hass: HomeAssistant, hk_driver, mock_get_source_ip
) -> None:
    """Test humanifying HomeKit changed event."""
    hass.config.components.add("recorder")
    with patch("homeassistant.components.homekit.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(hass, "homekit", {"homekit": {}})
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_HOMEKIT_CHANGED,
                {
                    ATTR_ENTITY_ID: "lock.front_door",
                    ATTR_DISPLAY_NAME: "Front Door",
                    ATTR_SERVICE: "lock",
                },
            ),
            MockRow(
                EVENT_HOMEKIT_CHANGED,
                {
                    ATTR_ENTITY_ID: "cover.window",
                    ATTR_DISPLAY_NAME: "Window",
                    ATTR_SERVICE: "set_cover_position",
                    ATTR_VALUE: 75,
                },
            ),
        ],
    )

    assert event1["name"] == "HomeKit"
    assert event1["domain"] == DOMAIN_HOMEKIT
    assert event1["message"] == "send command lock for Front Door"
    assert event1["entity_id"] == "lock.front_door"

    assert event2["name"] == "HomeKit"
    assert event2["domain"] == DOMAIN_HOMEKIT
    assert event2["message"] == "send command set_cover_position to 75 for Window"
    assert event2["entity_id"] == "cover.window"


async def test_bridge_with_triggers(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we can setup a bridge with triggers and we ignore numeric states.

    Since numeric states are not supported by HomeKit as they require
    an above or below additional configuration which we have no way
    to input, we ignore them.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "demo", {"demo": {}})
    await hass.async_block_till_done()

    entry = entity_registry.async_get("cover.living_room_window")
    assert entry is not None
    device_id = entry.device_id

    entry = MockConfigEntry(
        domain=DOMAIN_HOMEKIT,
        source=SOURCE_ZEROCONF,
        data={
            "name": "HASS Bridge",
            "port": 12345,
        },
        options={
            "filter": {
                "exclude_domains": [],
                "exclude_entities": [],
                "include_domains": [],
                "include_entities": ["cover.living_room_window"],
            },
            "exclude_accessory_mode": True,
            "mode": "bridge",
            "devices": [device_id],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.network.async_get_source_ip",
            return_value="1.2.3.4",
        ),
        patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        "requires additional inputs which are not supported by HomeKit" in caplog.text
    )
