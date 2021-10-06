"""Test UPnP/IGD config flow."""

from datetime import timedelta

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_HOSTNAME,
    CONFIG_ENTRY_SCAN_INTERVAL,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import (
    TEST_DISCOVERY,
    TEST_FRIENDLY_NAME,
    TEST_HOSTNAME,
    TEST_LOCATION,
    TEST_ST,
    TEST_UDN,
    TEST_USN,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures(
    "ssdp_instant_discovery", "mock_setup_entry", "mock_get_source_ip"
)
async def test_flow_ssdp(hass: HomeAssistant):
    """Test config flow: discovered + configured through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"

    # Confirm via step ssdp_confirm.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
    }


@pytest.mark.usefixtures("mock_get_source_ip")
async def test_flow_ssdp_incomplete_discovery(hass: HomeAssistant):
    """Test config flow: incomplete discovery through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: TEST_LOCATION,
            ssdp.ATTR_SSDP_ST: TEST_ST,
            ssdp.ATTR_SSDP_USN: TEST_USN,
            # ssdp.ATTR_UPNP_UDN: TEST_UDN,  # Not provided.
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "incomplete_discovery"


@pytest.mark.usefixtures("mock_get_source_ip")
async def test_flow_ssdp_discovery_ignored(hass: HomeAssistant):
    """Test config flow: discovery through ssdp, but ignored, as hostname is used by existing config entry."""
    # Existing entry.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN + "2",
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
        },
        options={CONFIG_ENTRY_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)

    # Discovered via step ssdp, but ignored.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "discovery_ignored"


@pytest.mark.usefixtures(
    "ssdp_instant_discovery", "mock_setup_entry", "mock_get_source_ip"
)
async def test_flow_user(hass: HomeAssistant):
    """Test config flow: discovered + configured through user."""
    # Discovered via step user.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Confirmed via step user.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"unique_id": TEST_USN},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
    }


@pytest.mark.usefixtures(
    "ssdp_instant_discovery", "mock_setup_entry", "mock_get_source_ip"
)
async def test_flow_import(hass: HomeAssistant):
    """Test config flow: configured through configuration.yaml."""
    # Discovered via step import.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
    }


@pytest.mark.usefixtures("ssdp_instant_discovery", "mock_get_source_ip")
async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test config flow: configured through configuration.yaml, but existing config entry."""
    # Existing entry.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
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


@pytest.mark.usefixtures("ssdp_no_discovery", "mock_get_source_ip")
async def test_flow_import_no_devices_found(hass: HomeAssistant):
    """Test config flow: no devices found, configured through configuration.yaml."""
    # Discovered via step import.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("ssdp_instant_discovery", "mock_get_source_ip")
async def test_options_flow(hass: HomeAssistant):
    """Test options flow."""
    # Set up config entry.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_HOSTNAME: TEST_HOSTNAME,
        },
        options={CONFIG_ENTRY_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()
    mock_device = hass.data[DOMAIN][config_entry.entry_id].device

    # Reset.
    mock_device.traffic_times_polled = 0
    mock_device.status_times_polled = 0

    # Forward time, ensure single poll after 30 (default) seconds.
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert mock_device.traffic_times_polled == 1
    assert mock_device.status_times_polled == 1

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
    assert mock_device.traffic_times_polled == 2
    assert mock_device.status_times_polled == 2

    # Now the updated interval takes effect.
    # Forward time, ensure single poll after 120 seconds.
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert mock_device.traffic_times_polled == 3
    assert mock_device.status_times_polled == 3

    # Forward time, ensure single poll after 180 seconds.
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=181))
    await hass.async_block_till_done()
    assert mock_device.traffic_times_polled == 4
    assert mock_device.status_times_polled == 4
