"""Test for Aladdin Connect init logic."""
from unittest.mock import MagicMock, patch

from AIOAladdinConnect.session_manager import InvalidPasswordError
from aiohttp import ClientConnectionError

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DEVICE_CONFIG_OPEN

from tests.common import AsyncMock, MockConfigEntry

CONFIG = {"username": "test-user", "password": "test-password"}
ID = "533255-1"


async def test_setup_get_doors_errors(hass: HomeAssistant) -> None:
    """Test component setup Get Doors Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_login_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test component setup Login Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id=ID,
    )
    config_entry.add_to_hass(hass)
    mock_aladdinconnect_api.login.return_value = False
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_setup_connection_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test component setup Login Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id=ID,
    )
    config_entry.add_to_hass(hass)
    mock_aladdinconnect_api.login.side_effect = ClientConnectionError
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_setup_component_no_error(hass: HomeAssistant) -> None:
    """Test component setup No Error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id=ID,
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


async def test_entry_password_fail(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test password fail during entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)
    mock_aladdinconnect_api.login = AsyncMock(return_value=False)
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_and_unload(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test loading and unloading Aladdin Connect entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id=ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_stale_device_removal(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test component setup missing door device is removed."""
    DEVICE_CONFIG_DOOR_2 = {
        "device_id": 533255,
        "door_number": 2,
        "name": "home 2",
        "status": "open",
        "link_status": "Connected",
        "serial": "12346",
        "model": "02",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id=ID,
    )
    config_entry.add_to_hass(hass)
    mock_aladdinconnect_api.get_doors = AsyncMock(
        return_value=[DEVICE_CONFIG_OPEN, DEVICE_CONFIG_DOOR_2]
    )
    config_entry_other = MockConfigEntry(
        domain="OtherDomain",
        data=CONFIG,
        unique_id="unique_id",
    )
    config_entry_other.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_entry_other = device_registry.async_get_or_create(
        config_entry_id=config_entry_other.entry_id,
        identifiers={("OtherDomain", "533255-2")},
    )
    device_registry.async_update_device(
        device_entry_other.id,
        add_config_entry_id=config_entry.entry_id,
        merge_identifiers={(DOMAIN, "533255-2")},
    )

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    device_registry = dr.async_get(hass)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2
    assert any((DOMAIN, "533255-1") in device.identifiers for device in device_entries)
    assert any((DOMAIN, "533255-2") in device.identifiers for device in device_entries)
    assert any(
        ("OtherDomain", "533255-2") in device.identifiers for device in device_entries
    )

    device_entries_other = dr.async_entries_for_config_entry(
        device_registry, config_entry_other.entry_id
    )
    assert len(device_entries_other) == 1
    assert any(
        (DOMAIN, "533255-2") in device.identifiers for device in device_entries_other
    )
    assert any(
        ("OtherDomain", "533255-2") in device.identifiers
        for device in device_entries_other
    )

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    mock_aladdinconnect_api.get_doors = AsyncMock(return_value=[DEVICE_CONFIG_OPEN])
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert any((DOMAIN, "533255-1") in device.identifiers for device in device_entries)
    assert not any(
        (DOMAIN, "533255-2") in device.identifiers for device in device_entries
    )
    assert not any(
        ("OtherDomain", "533255-2") in device.identifiers for device in device_entries
    )

    device_entries_other = dr.async_entries_for_config_entry(
        device_registry, config_entry_other.entry_id
    )

    assert len(device_entries_other) == 1
    assert any(
        ("OtherDomain", "533255-2") in device.identifiers
        for device in device_entries_other
    )
    assert any(
        (DOMAIN, "533255-2") in device.identifiers for device in device_entries_other
    )
