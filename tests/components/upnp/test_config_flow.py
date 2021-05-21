"""Test UPnP/IGD config flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_HOSTNAME,
    CONFIG_ENTRY_SCAN_INTERVAL,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DEFAULT_SCAN_INTERVAL,
    DISCOVERY_HOSTNAME,
    DISCOVERY_LOCATION,
    DISCOVERY_NAME,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_UNIQUE_ID,
    DISCOVERY_USN,
    DOMAIN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from .mock_device import MockDevice

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_flow_ssdp_discovery(hass: HomeAssistant):
    """Test config flow: discovered + configured through ssdp."""
    udn = "uuid:device_1"
    location = "dummy"
    mock_device = MockDevice(udn)
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]
    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(
        Device, "async_discover", AsyncMock(return_value=discoveries)
    ), patch.object(
        Device, "async_supplement_discovery", AsyncMock(return_value=discoveries[0])
    ):
        # Discovered via step ssdp.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data={
                ssdp.ATTR_SSDP_LOCATION: location,
                ssdp.ATTR_SSDP_ST: mock_device.device_type,
                ssdp.ATTR_SSDP_USN: mock_device.usn,
                ssdp.ATTR_UPNP_UDN: mock_device.udn,
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "ssdp_confirm"

        # Confirm via step ssdp_confirm.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        }


async def test_flow_ssdp_incomplete_discovery(hass: HomeAssistant):
    """Test config flow: incomplete discovery through ssdp."""
    udn = "uuid:device_1"
    location = "dummy"
    mock_device = MockDevice(udn)

    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: location,
            ssdp.ATTR_SSDP_ST: mock_device.device_type,
            ssdp.ATTR_SSDP_USN: mock_device.usn,
            # ssdp.ATTR_UPNP_UDN: mock_device.udn,  # Not provided.
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "incomplete_discovery"


async def test_flow_ssdp_discovery_ignored(hass: HomeAssistant):
    """Test config flow: discovery through ssdp, but ignored."""
    udn = "uuid:device_random_1"
    location = "dummy"
    mock_device = MockDevice(udn)

    # Existing entry.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: "uuid:device_random_2",
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        },
        options={CONFIG_ENTRY_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)

    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]

    with patch.object(
        Device, "async_supplement_discovery", AsyncMock(return_value=discoveries[0])
    ):
        # Discovered via step ssdp, but ignored.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data={
                ssdp.ATTR_SSDP_LOCATION: location,
                ssdp.ATTR_SSDP_ST: mock_device.device_type,
                ssdp.ATTR_SSDP_USN: mock_device.usn,
                ssdp.ATTR_UPNP_UDN: mock_device.udn,
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "discovery_ignored"


async def test_flow_user(hass: HomeAssistant):
    """Test config flow: discovered + configured through user."""
    udn = "uuid:device_1"
    location = "dummy"
    mock_device = MockDevice(udn)
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]

    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(
        Device, "async_discover", AsyncMock(return_value=discoveries)
    ), patch.object(
        Device, "async_supplement_discovery", AsyncMock(return_value=discoveries[0])
    ):
        # Discovered via step user.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        # Confirmed via step user.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"unique_id": mock_device.unique_id},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        }


async def test_flow_import(hass: HomeAssistant):
    """Test config flow: discovered + configured through configuration.yaml."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    location = "dummy"
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]

    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(
        Device, "async_discover", AsyncMock(return_value=discoveries)
    ), patch.object(
        Device, "async_supplement_discovery", AsyncMock(return_value=discoveries[0])
    ):
        # Discovered via step import.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        }


async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test config flow: discovered, but already configured."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)

    # Existing entry.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        },
        options={CONFIG_ENTRY_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)

    # Discovered via step import.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_incomplete(hass: HomeAssistant):
    """Test config flow: incomplete discovery, configured through configuration.yaml."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    location = "dummy"
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            # DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]

    with patch.object(Device, "async_discover", AsyncMock(return_value=discoveries)):
        # Discovered via step import.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "incomplete_discovery"


async def test_options_flow(hass: HomeAssistant):
    """Test options flow."""
    # Set up config entry.
    udn = "uuid:device_1"
    location = "http://192.168.1.1/desc.xml"
    mock_device = MockDevice(udn)
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_ST: mock_device.device_type,
            CONFIG_ENTRY_HOSTNAME: mock_device.hostname,
        },
        options={CONFIG_ENTRY_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)

    config = {
        # no upnp, ensures no import-flow is started.
    }
    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(Device, "async_discover", AsyncMock(return_value=discoveries)):
        # Initialisation of component.
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()
        mock_device.times_polled = 0  # Reset.

        # Forward time, ensure single poll after 30 (default) seconds.
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()
        assert mock_device.times_polled == 1

        # Options flow with no input results in form.
        result = await hass.config_entries.options.async_init(
            config_entry.entry_id,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        # Options flow with input results in update to entry.
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONFIG_ENTRY_SCAN_INTERVAL: 60},
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            CONFIG_ENTRY_SCAN_INTERVAL: 60,
        }

        # Forward time, ensure single poll after 60 seconds, still from original setting.
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done()
        assert mock_device.times_polled == 2

        # Now the updated interval takes effect.
        # Forward time, ensure single poll after 120 seconds.
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=121))
        await hass.async_block_till_done()
        assert mock_device.times_polled == 3

        # Forward time, ensure single poll after 180 seconds.
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=181))
        await hass.async_block_till_done()
        assert mock_device.times_polled == 4
