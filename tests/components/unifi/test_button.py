"""UniFi Network button platform tests."""

from aiounifi.websocket import WebsocketState

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
)
from homeassistant.components.unifi.const import (
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_controller import (
    setup_unifi_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_restart_device_button(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test restarting device button."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "ip": "10.0.0.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "switch",
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ],
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 1

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("button.switch_restart")
    assert ent_reg_entry.unique_id == "device_restart-00:00:00:00:01:01"
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Validate state object
    button = hass.states.get("button.switch_restart")
    assert button is not None
    assert button.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    # Send restart device command
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/devmgr",
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.switch_restart"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "restart",
        "mac": "00:00:00:00:01:01",
        "reboot_type": "soft",
    }

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("button.switch_restart").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("button.switch_restart").state != STATE_UNAVAILABLE
