"""Tests for VegeHub config flow."""

import asyncio
from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.vegehub.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker

# Mock data for testing
TEST_IP = "192.168.0.100"
TEST_MAC = "A1:B2:C3:D4:E5:F6"
TEST_SIMPLE_MAC = "a1b2c3d4e5f6"
TEST_HOSTNAME = "VegeHub"

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(TEST_IP),
    ip_addresses=[ip_address(TEST_IP)],
    port=80,
    hostname=f"{TEST_HOSTNAME}.local.",
    type="mock_type",
    name="myVege",
    properties={
        zeroconf.ATTR_PROPERTIES_ID: TEST_HOSTNAME,
        "version": "5.1.1",
    },
)


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp.ClientSession."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        mocker.get(
            "http://192.168.0.100/api/update/send",
            status=200,
            text="",
        )
        mocker.post(
            "http://192.168.0.100/api/config/set",
            status=200,
            json={"error": "success"},
        )
        mocker.post(
            "http://192.168.0.100/api/info/get",
            status=200,
            json={
                "wifi": {
                    "ssid": "YourWiFiName",
                    "strength": "-25",
                    "chan": "4",
                    "ip": TEST_IP,
                    "status": "3",
                    "mac_addr": TEST_MAC,
                },
                "hub": {
                    "first_boot": False,
                    "page_updated": False,
                    "error_message": 0,
                    "num_channels": 4,
                    "num_actuators": 1,
                    "version": "5.1.2",
                    "agenda": 1,
                    "batt_v": 9.0,
                    "num_vsens": 0,
                    "is_ac": 0,
                    "has_sd": 0,
                    "on_ap": 0,
                },
                "error": "success",
            },
        )
        mocker.post(
            "http://192.168.0.100/api/config/get",
            status=200,
            json={
                "hub": {
                    "name": TEST_HOSTNAME,
                    "model": "Undefined",
                    "firmware_version": "5.1.2",
                    "firmware_url": "https://vegecloud.com/firmware/VG-HUB/latest.json",
                    "utc_offset": -21600,
                    "sample_period": 10,
                    "update_period": 60,
                    "blink_update": 1,
                    "report_voltage": 1,
                    "server_url": "http://homeassistant.local:8123/api/vegehub/update",
                    "update_urls": [],
                    "server_type": 3,
                    "server_channel": "",
                    "server_user": "",
                    "static_ip_addr": "",
                    "dns": "",
                    "subnet": "",
                    "gateway": "",
                    "current_ip_addr": "192.168.0.123",
                    "power_mode": 1,
                    "agenda": 1,
                    "onboard_sensor_poll_rate": 1800,
                    "remote_sensor_poll_rate": 1800,
                },
                "api_key": "7C9EBD4B49D8",
                "wifi": {
                    "type": 0,
                    "wifi_ssid": "YourWiFiName",
                    "wifi_pw": "your secure wifi passphrase",
                    "ap_pw": "vegetronix",
                },
                "error": "success",
            },
        )
        yield mocker


@pytest.fixture
def setup_mock_config_flow():
    """Fixture to set up the mock config flow."""
    with (
        patch(
            "socket.gethostname",
            return_value=TEST_HOSTNAME,
        ),
    ):
        yield


async def test_user_flow_success(
    hass: HomeAssistant, setup_mock_config_flow, mock_aiohttp_session
) -> None:
    """Test the user flow with successful configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["mac_address"] == TEST_SIMPLE_MAC
    # Confirm that the entry was created
    entries = hass.config_entries.async_entries(domain=DOMAIN)
    assert len(entries) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the user flow when the device cannot be connected."""
    with patch(
        "homeassistant.components.vegehub.config_flow.VegeHubConfigFlow._get_device_mac",
        return_value="",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ip_address": TEST_IP}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_success(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOSTNAME
    assert result["data"]["mac_address"] == TEST_SIMPLE_MAC


async def test_user_options(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test zeroconf flow when the device already exists in the system."""
    with patch(
        "homeassistant.components.vegehub.config_flow.VegeHubConfigFlow.async_set_unique_id",
        side_effect=lambda unique_id: None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DISCOVERY_INFO,
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        # Confirm that the entry was created
        entries = hass.config_entries.async_entries(domain=DOMAIN)
        assert len(entries) == 1

        # Step 3: Initialize the options flow
        result = await hass.config_entries.options.async_init(entries[0].entry_id)

        # Assert that it reaches the expected step in the options flow
        assert result["type"] == "form"
        assert result["step_id"] == "init"

        # Simulate user input for options flow
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "user_act_duration": 75
            },  # Replace with your options flow's user input
        )

        # Validate the result, like completing the options flow
        assert result["type"] == "create_entry"
        assert result["data"]["user_act_duration"] == 75
