"""Test the Aladdin Connect Cover."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
import homeassistant.components.aladdin_connect.cover as cover
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
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


async def test_setup_component_typeerror(hass: HomeAssistant) -> None:
    """Test component setup TypeError."""
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
        side_effect=TypeError,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_component_keyerror(hass: HomeAssistant) -> None:
    """Test component setup KeyError."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        side_effect=KeyError,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_component_nameerror(hass: HomeAssistant) -> None:
    """Test component setup Namerror."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        side_effect=NameError,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_component_valueerror(hass: HomeAssistant) -> None:
    """Test component setup ValueError."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        side_effect=ValueError,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_component_noerror(hass: HomeAssistant) -> None:
    """Test component setup KeyError."""
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


async def test_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading Aladdin Connect entry."""
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

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_open_cover(hass: HomeAssistant) -> None:
    """Test component setup KeyError."""
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
    # assert hass.states.get("cover.home").is_available is False
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=[DEVICE_CONFIG_BAD_NO_DOOR],
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "cover.home"}, blocking=True
        )


async def test_yaml_info_cover(hass):
    """Test setup YAML import."""
    assert COVER_DOMAIN not in hass.config.components
    hass.async_create_task = AsyncMock()
    await cover.async_setup_platform(hass, YAML_CONFIG, None)
    await hass.async_block_till_done()
