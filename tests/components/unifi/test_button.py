"""UniFi Network button platform tests."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonDeviceClass
from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_controller import setup_unifi_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_restart_device_button(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, websocket_mock
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
    await websocket_mock.disconnect()
    assert hass.states.get("button.switch_restart").state == STATE_UNAVAILABLE

    # Controller reconnects
    await websocket_mock.reconnect()
    assert hass.states.get("button.switch_restart").state != STATE_UNAVAILABLE


async def test_power_cycle_poe(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, websocket_mock
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
                "port_table": [
                    {
                        "media": "GE",
                        "name": "Port 1",
                        "port_idx": 1,
                        "poe_caps": 7,
                        "poe_class": "Class 4",
                        "poe_enable": True,
                        "poe_mode": "auto",
                        "poe_power": "2.56",
                        "poe_voltage": "53.40",
                        "portconf_id": "1a1",
                        "port_poe": True,
                        "up": True,
                    },
                ],
            }
        ],
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 2

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("button.switch_port_1_power_cycle")
    assert ent_reg_entry.unique_id == "power_cycle-00:00:00:00:01:01_1"
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Validate state object
    button = hass.states.get("button.switch_port_1_power_cycle")
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
        {"entity_id": "button.switch_port_1_power_cycle"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "power-cycle",
        "mac": "00:00:00:00:01:01",
        "port_idx": 1,
    }

    # Availability signalling

    # Controller disconnects
    await websocket_mock.disconnect()
    assert (
        hass.states.get("button.switch_port_1_power_cycle").state == STATE_UNAVAILABLE
    )

    # Controller reconnects
    await websocket_mock.reconnect()
    assert (
        hass.states.get("button.switch_port_1_power_cycle").state != STATE_UNAVAILABLE
    )
