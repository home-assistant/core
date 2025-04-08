"""Tests for the SwitchBot Cloud integration init."""

from unittest.mock import patch

from aiohttp.test_utils import TestClient
import pytest
from switchbot_api import CannotConnect, Device, InvalidAuth, PowerState, Remote

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from . import configure_integration

from tests.typing import ClientSessionGenerator


@pytest.fixture
def mock_list_devices():
    """Mock list_devices."""
    with patch.object(SwitchBotAPI, "list_devices") as mock_list_devices:
        yield mock_list_devices


@pytest.fixture
def mock_get_status():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "get_status") as mock_get_status:
        yield mock_get_status


@pytest.fixture
def mock_get_webook_configuration():
    """Mock get_status."""
    with patch.object(
        SwitchBotAPI, "get_webook_configuration"
    ) as mock_get_webook_configuration:
        yield mock_get_webook_configuration


@pytest.fixture
def mock_delete_webhook():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "delete_webhook") as mock_delete_webhook:
        yield mock_delete_webhook


@pytest.fixture
def mock_setup_webhook():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "setup_webhook") as mock_setup_webhook:
        yield mock_setup_webhook


@pytest.fixture
async def mock_client(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Create http client for webhooks."""
    await async_setup_component(hass, "webhook", {})
    return await hass_client()


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test successful setup of entry."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": ["https://example.com"]}
    mock_list_devices.return_value = [
        Remote(
            version="V1.0",
            deviceId="air-conditonner-id-1",
            deviceName="air-conditonner-name-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
        Device(
            version="V1.0",
            deviceId="plug-id-1",
            deviceName="plug-name-1",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="plug-id-2",
            deviceName="plug-name-2",
            remoteType="DIY Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="meter-pro-1",
            deviceName="meter-pro-name-1",
            deviceType="MeterPro(CO2)",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="hub2-1",
            deviceName="hub2-name-1",
            deviceType="Hub 2",
            hubDeviceId="test-hub-id",
        ),
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()
    mock_get_webook_configuration.assert_called_once()
    mock_delete_webhook.assert_called_once()
    mock_setup_webhook.assert_called_once()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (InvalidAuth, ConfigEntryState.SETUP_ERROR),
        (CannotConnect, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_fails_when_listing_devices(
    hass: HomeAssistant,
    error: Exception,
    state: ConfigEntryState,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test error handling when list_devices in setup of entry."""
    mock_list_devices.side_effect = error
    entry = await configure_integration(hass)
    assert entry.state == state

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_not_called()


async def test_setup_entry_fails_when_refreshing(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test error handling in get_status in setup of entry."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="test-id",
            deviceName="test-name",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        )
    ]
    mock_get_status.side_effect = CannotConnect
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()


async def test_posting_to_webhook(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
    mock_client,
) -> None:
    """Test handler webhook call."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": ["https://example.com"]}
    mock_list_devices.return_value = [
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    # fire webhook
    await mock_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "eventType": "changeReport",
            "eventVersion": "1",
            "context": {"deviceType": "...", "deviceMac": "vacuum-1"},
        },
    )

    await hass.async_block_till_done()

    mock_setup_webhook.assert_called_once()
