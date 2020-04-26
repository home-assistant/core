"""Tests for the GogoGate2 component."""
from unittest.mock import MagicMock

from pygogogate2 import Gogogate2API

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .common import ComponentFactory


async def test_import(hass: HomeAssistant, component_factory: ComponentFactory) -> None:
    """Test importing of file based config."""
    api0 = MagicMock(spec=Gogogate2API)
    api0.get_devices.return_value = [
        {"door": 0, "name": "door0", "status": "open"},
    ]
    api1 = MagicMock(spec=Gogogate2API)
    api1.get_devices.return_value = [{"door": 1, "name": "door1", "status": "closed"}]

    def new_api(username: str, password: str, ip_address: str) -> Gogogate2API:
        if ip_address == "127.0.1.0":
            return api0
        if ip_address == "127.0.1.1":
            return api1

    component_factory.api_class_mock.side_effect = new_api

    await component_factory.configure_component(
        cover_config=[
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover0",
                CONF_IP_ADDRESS: "127.0.1.0",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            },
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover1",
                CONF_IP_ADDRESS: "127.0.1.1",
                CONF_USERNAME: "user1",
                CONF_PASSWORD: "password1",
            },
        ]
    )
    entity_ids = hass.states.async_entity_ids(COVER_DOMAIN)
    assert entity_ids is not None
    assert len(entity_ids) == 2
    assert "cover.cover0" in entity_ids
    assert "cover.cover1" in entity_ids

    await component_factory.unload()


async def test_cover(hass: HomeAssistant, component_factory: ComponentFactory) -> None:
    """Test cover."""
    await component_factory.configure_component()
    api_mock = await component_factory.run_config_flow(
        config_data={
            CONF_NAME: "cover0",
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        }
    )

    assert hass.states.async_entity_ids(COVER_DOMAIN)

    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["friendly_name"] == "cover0"
    assert state.attributes["supported_features"] == 3
    assert state.attributes["device_class"] == "garage"

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_OPEN

    api_mock.get_status.side_effect = None
    api_mock.get_status.return_value = "closed"
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_CLOSED

    api_mock.get_status.side_effect = Exception("ERROR")
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_UNAVAILABLE

    api_mock.get_status.side_effect = None
    api_mock.get_status.return_value = "open"
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_OPEN

    api_mock.get_status.side_effect = Exception("ERROR")
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_UNAVAILABLE

    api_mock.get_status.side_effect = None
    api_mock.get_status.return_value = "open"
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_OPEN

    api_mock.close_device.reset_mock()
    api_mock.open_device.reset_mock()
    api_mock.get_status.side_effect = None
    api_mock.get_status.return_value = "closed"
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": "cover.cover0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_CLOSED
    api_mock.close_device.assert_called()
    api_mock.open_device.assert_not_called()

    api_mock.close_device.reset_mock()
    api_mock.open_device.reset_mock()
    api_mock.get_status.side_effect = None
    api_mock.get_status.return_value = "open"
    await hass.services.async_call("cover", "open_cover", {"entity_id": "cover.cover0"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.cover0")
    assert state
    assert state.state == STATE_OPEN
    api_mock.close_device.assert_not_called()
    api_mock.open_device.assert_called()

    await component_factory.unload()
