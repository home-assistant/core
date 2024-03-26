"""Test the integration init functionality."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeconnect.api import HomeConnectAppliance
import pytest
from requests import HTTPError

from homeassistant.components.home_connect.api import ConfigEntryAuth
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from .conftest import MOCK_APPLIANCES_PROPERTIES

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_APPLIANCE_DISHWASHER_PROPERTIES = MOCK_APPLIANCES_PROPERTIES["Dishwasher"]

SERVICE_KV_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "set_option_active",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
            "unit": "",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_option_selected",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "change_setting",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
]

SERVICE_COMMAND_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "pause_program",
        "service_data": {
            "device_id": "DEVICE_ID",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "resume_program",
        "service_data": {
            "device_id": "DEVICE_ID",
        },
        "blocking": True,
    },
]


SERVICE_PROGRAM_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "select_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": "",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "start_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": "",
            "key": "",
            "value": "",
            "unit": "C",
        },
        "blocking": True,
    },
]


async def test_setup(
    config_entry_auth,
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test setting up the integration."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


@patch.object(ConfigEntryAuth, "get_devices")
async def test_update_throttle(
    get_devices,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    platforms: list[Platform],
) -> None:
    """Test to check Throttle functionality."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    assert await integration_setup()
    assert get_devices.call_count == 0
    assert config_entry.state == ConfigEntryState.LOADED


@patch.object(
    ConfigEntryAuth, "get_devices", side_effect=HTTPError(response=MagicMock())
)
async def test_http_error(
    get_devices,
    bypass_throttle,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Test HTTP errors during setup integration."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    future = utcnow() + timedelta(minutes=20)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert await integration_setup()

    assert get_devices.call_count == 1
    assert config_entry.state == ConfigEntryState.LOADED


async def test_services(
    bypass_throttle,
    config_entry_auth_devices,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Create and test services."""
    appliance = MagicMock(
        autospec=HomeConnectAppliance, **MOCK_APPLIANCE_DISHWASHER_PROPERTIES
    )
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    future = utcnow() + timedelta(minutes=80)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert await integration_setup()

    assert config_entry.state == ConfigEntryState.LOADED
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_APPLIANCE_DISHWASHER_PROPERTIES["haId"])},
    )
    with patch(
        "homeassistant.components.home_connect._get_appliance_by_device_id"
    ) as service_call_tracking:
        service_call_tracking.return_value = appliance
        service_calls = (
            SERVICE_KV_CALL_PARAMS
            + SERVICE_PROGRAM_CALL_PARAMS
            + SERVICE_COMMAND_CALL_PARAMS
        )
        for service_call in service_calls:
            service_call["service_data"]["device_id"] = device_entry.id
            await hass.services.async_call(**service_call)
            await hass.async_block_till_done()

        assert service_call_tracking.call_count == len(service_calls)

    # _get_appliance_by_device_id tests
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()

    with pytest.raises(ValueError):
        service_call["service_data"]["device_id"] = "DOES_NOT_EXISTS"
        await hass.services.async_call(**service_call)
        await hass.async_block_till
