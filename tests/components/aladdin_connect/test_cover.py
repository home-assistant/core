"""Test the Aladdin Connect Cover."""
from unittest.mock import patch

import pytest

from homeassistant.components.aladdin_connect.const import DOMAIN
import homeassistant.components.aladdin_connect.cover as cover
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

YAML_CONFIG = {"username": "test-user", "password": "test-password"}

DEVICE_CONFIG_OPEN = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
    "link_status": "Connected",
}

DEVICE_CONFIG_OPENING = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "opening",
    "link_status": "Connected",
}

DEVICE_CONFIG_CLOSED = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "closed",
    "link_status": "Connected",
}

DEVICE_CONFIG_CLOSING = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "closing",
    "link_status": "Connected",
}

DEVICE_CONFIG_DISCONNECTED = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
    "link_status": "Disconnected",
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


@pytest.mark.parametrize(
    "side_effect",
    [
        (TypeError),
        (KeyError),
        (NameError),
        (ValueError),
    ],
)
async def test_setup_get_doors_errors(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test component setup Get Doors Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        side_effect=side_effect,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "side_effect",
    [
        (TypeError),
        (KeyError),
        (NameError),
        (ValueError),
    ],
)
async def test_setup_login_error(hass: HomeAssistant, side_effect: Exception) -> None:
    """Test component setup Login Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        side_effect=side_effect,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_component_noerror(hass: HomeAssistant) -> None:
    """Test component setup No Error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ):

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_cover_operation(hass: HomeAssistant) -> None:
    """Test component setup open cover, close cover."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_OPEN],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert COVER_DOMAIN in hass.config.components

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.open_door",
        return_value=True,
    ):
        await hass.services.async_call(
            "cover", "open_cover", {"entity_id": "cover.home"}, blocking=True
        )

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.close_door",
        return_value=True,
    ):
        await hass.services.async_call(
            "cover", "close_cover", {"entity_id": "cover.home"}, blocking=True
        )
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_CLOSED],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state == STATE_CLOSED

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_OPEN],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state == STATE_OPEN

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_OPENING],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state == STATE_OPENING

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_CLOSING],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state == STATE_CLOSING

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_BAD],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_BAD_NO_DOOR],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )
    assert hass.states.get("cover.home").state


async def test_yaml_import(hass: HomeAssistant, caplog: pytest.LogCaptureFixture):
    """Test setup YAML import."""
    assert COVER_DOMAIN not in hass.config.components

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_CLOSED],
    ):
        await cover.async_setup_platform(hass, YAML_CONFIG, None)
        await hass.async_block_till_done()

    assert "Configuring Aladdin Connect through yaml is deprecated" in caplog.text

    assert hass.config_entries.async_entries(DOMAIN)
    config_data = hass.config_entries.async_entries(DOMAIN)[0].data
    assert config_data[CONF_USERNAME] == "test-user"
    assert config_data[CONF_PASSWORD] == "test-password"
