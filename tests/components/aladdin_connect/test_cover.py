"""Test the Aladdin Connect Cover."""
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.components.aladdin_connect.cover import SCAN_INTERVAL
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {"username": "test-user", "password": "test-password"}

DEVICE_CONFIG_OPEN = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
    "link_status": "Connected",
    "serial": "12345",
}

DEVICE_CONFIG_OPENING = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "opening",
    "link_status": "Connected",
    "serial": "12345",
}

DEVICE_CONFIG_CLOSED = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "closed",
    "link_status": "Connected",
    "serial": "12345",
}

DEVICE_CONFIG_CLOSING = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "closing",
    "link_status": "Connected",
    "serial": "12345",
}

DEVICE_CONFIG_DISCONNECTED = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
    "link_status": "Disconnected",
    "serial": "12345",
}

DEVICE_CONFIG_BAD = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
}
DEVICE_CONFIG_BAD_NO_DOOR = {
    "device_id": 533255,
    "door_number": 2,
    "name": "home",
    "status": "open",
    "link_status": "Disconnected",
}


async def test_cover_operation(
    hass: HomeAssistant,
    mock_aladdinconnect_api: MagicMock,
) -> None:
    """Test Cover Operation states (open,close,opening,closing) cover."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    mock_aladdinconnect_api.async_get_door_status = AsyncMock(return_value=STATE_OPEN)
    mock_aladdinconnect_api.get_door_status.return_value = STATE_OPEN
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert COVER_DOMAIN in hass.config.components

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.home"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.home").state == STATE_OPEN

    mock_aladdinconnect_api.async_get_door_status = AsyncMock(return_value=STATE_CLOSED)
    mock_aladdinconnect_api.get_door_status.return_value = STATE_CLOSED
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.home"},
            blocking=True,
        )
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

    assert hass.states.get("cover.home").state == STATE_CLOSED

    mock_aladdinconnect_api.async_get_door_status = AsyncMock(
        return_value=STATE_CLOSING
    )
    mock_aladdinconnect_api.get_door_status.return_value = STATE_CLOSING

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()
    assert hass.states.get("cover.home").state == STATE_CLOSING

    mock_aladdinconnect_api.async_get_door_status = AsyncMock(
        return_value=STATE_OPENING
    )
    mock_aladdinconnect_api.get_door_status.return_value = STATE_OPENING

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()
    assert hass.states.get("cover.home").state == STATE_OPENING

    mock_aladdinconnect_api.async_get_door_status = AsyncMock(return_value=None)
    mock_aladdinconnect_api.get_door_status.return_value = None
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.home"},
            blocking=True,
        )
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

    assert hass.states.get("cover.home").state == STATE_UNKNOWN
