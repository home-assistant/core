"""Test UPnP/IGD config flow."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_HOST,
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
    ST_IGD_V1,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_DISCOVERY,
    TEST_FRIENDLY_NAME,
    TEST_HOST,
    TEST_LOCATION,
    TEST_MAC_ADDRESS,
    TEST_ST,
    TEST_UDN,
    TEST_USN,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_flow_ssdp(hass: HomeAssistant) -> None:
    """Test config flow: discovered + configured through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    # Confirm via step ssdp_confirm.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
        CONFIG_ENTRY_LOCATION: TEST_LOCATION,
        CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        CONFIG_ENTRY_HOST: TEST_HOST,
    }


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_flow_ssdp_ignore(hass: HomeAssistant) -> None:
    """Test config flow: discovered + ignore through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    # Ignore entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": TEST_USN, "title": TEST_FRIENDLY_NAME},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
        CONFIG_ENTRY_LOCATION: TEST_LOCATION,
        CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        CONFIG_ENTRY_HOST: TEST_HOST,
    }


@pytest.mark.usefixtures("mock_get_source_ip")
async def test_flow_ssdp_incomplete_discovery(hass: HomeAssistant) -> None:
    """Test config flow: incomplete discovery through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn=TEST_USN,
            ssdp_st=TEST_ST,
            ssdp_location=TEST_LOCATION,
            upnp={
                ssdp.ATTR_UPNP_DEVICE_TYPE: ST_IGD_V1,
                # ssdp.ATTR_UPNP_UDN: TEST_UDN,  # Not provided.
            },
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "incomplete_discovery"


@pytest.mark.usefixtures("mock_get_source_ip")
async def test_flow_ssdp_non_igd_device(hass: HomeAssistant) -> None:
    """Test config flow: incomplete discovery through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn=TEST_USN,
            ssdp_st=TEST_ST,
            ssdp_location=TEST_LOCATION,
            ssdp_all_locations=[TEST_LOCATION],
            upnp={
                ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:WFADevice:1",  # Non-IGD
                ssdp.ATTR_UPNP_UDN: TEST_UDN,
            },
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "non_igd_device"


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
    "mock_no_mac_address_from_host",
)
async def test_flow_ssdp_no_mac_address(hass: HomeAssistant) -> None:
    """Test config flow: discovered + configured through ssdp."""
    # Discovered via step ssdp.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    # Confirm via step ssdp_confirm.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
        CONFIG_ENTRY_LOCATION: TEST_LOCATION,
        CONFIG_ENTRY_MAC_ADDRESS: None,
        CONFIG_ENTRY_HOST: TEST_HOST,
    }


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_flow_ssdp_discovery_changed_udn_match_mac(hass: HomeAssistant) -> None:
    """Test config flow: discovery through ssdp, same device, but new UDN, matched on mac address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        source=config_entries.SOURCE_SSDP,
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    # New discovery via step ssdp.
    new_udn = TEST_UDN + "2"
    new_discovery = deepcopy(TEST_DISCOVERY)
    new_discovery.ssdp_usn = f"{new_udn}::{TEST_ST}"
    new_discovery.upnp["_udn"] = new_udn
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=new_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "config_entry_updated"


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_flow_ssdp_discovery_changed_udn_match_host(hass: HomeAssistant) -> None:
    """Test config flow: discovery through ssdp, same device, but new UDN, matched on mac address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_HOST: TEST_HOST,
        },
        source=config_entries.SOURCE_SSDP,
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    # New discovery via step ssdp.
    new_udn = TEST_UDN + "2"
    new_discovery = deepcopy(TEST_DISCOVERY)
    new_discovery.ssdp_usn = f"{new_udn}::{TEST_ST}"
    new_discovery.upnp["_udn"] = new_udn
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=new_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "config_entry_updated"


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
)
async def test_flow_ssdp_discovery_changed_udn_but_st_differs(
    hass: HomeAssistant,
) -> None:
    """Test config flow: discovery through ssdp, same device, but new UDN, and different ST, so not matched --> new discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        source=config_entries.SOURCE_SSDP,
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    # UDN + mac address different: New discovery via step ssdp.
    new_udn = TEST_UDN + "2"
    with patch(
        "homeassistant.components.upnp.device.get_mac_address",
        return_value=TEST_MAC_ADDRESS + "2",
    ):
        new_discovery = deepcopy(TEST_DISCOVERY)
        new_discovery.ssdp_usn = f"{new_udn}::{TEST_ST}"
        new_discovery.upnp["_udn"] = new_udn
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=new_discovery,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "ssdp_confirm"

    # UDN + ST different: New discovery via step ssdp.
    with patch(
        "homeassistant.components.upnp.device.get_mac_address",
        return_value=TEST_MAC_ADDRESS,
    ):
        new_st = TEST_ST + "2"
        new_discovery = deepcopy(TEST_DISCOVERY)
        new_discovery.ssdp_usn = f"{new_udn}::{new_st}"
        new_discovery.ssdp_st = new_st
        new_discovery.upnp["_udn"] = new_udn
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=new_discovery,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "ssdp_confirm"


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_flow_ssdp_discovery_changed_location(hass: HomeAssistant) -> None:
    """Test config flow: discovery through ssdp, same device, but new location."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        source=config_entries.SOURCE_SSDP,
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    # Discovery via step ssdp.
    new_location = TEST_DISCOVERY.ssdp_location + "2"
    new_discovery = deepcopy(TEST_DISCOVERY)
    new_discovery.ssdp_location = new_location
    new_discovery.ssdp_all_locations = {new_location}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=new_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test if location is updated.
    assert entry.data[CONFIG_ENTRY_LOCATION] == new_location


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_flow_ssdp_discovery_ignored_entry(hass: HomeAssistant) -> None:
    """Test config flow: discovery through ssdp, same device, but new UDN, matched on mac address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_flow_ssdp_discovery_changed_udn_ignored_entry(
    hass: HomeAssistant,
) -> None:
    """Test config flow: discovery through ssdp, same device, but new UDN, matched on mac address, entry ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    # New discovery via step ssdp.
    new_udn = TEST_UDN + "2"
    new_discovery = deepcopy(TEST_DISCOVERY)
    new_discovery.ssdp_usn = f"{new_udn}::{TEST_ST}"
    new_discovery.upnp["_udn"] = new_udn
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=new_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "discovery_ignored"


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_flow_user(hass: HomeAssistant) -> None:
    """Test config flow: discovered + configured through user."""
    # Discovered via step user.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Confirmed via step user.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"unique_id": TEST_USN},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FRIENDLY_NAME
    assert result["data"] == {
        CONFIG_ENTRY_ST: TEST_ST,
        CONFIG_ENTRY_UDN: TEST_UDN,
        CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
        CONFIG_ENTRY_LOCATION: TEST_LOCATION,
        CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        CONFIG_ENTRY_HOST: TEST_HOST,
    }


@pytest.mark.usefixtures(
    "ssdp_no_discovery",
    "mock_setup_entry",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_flow_user_no_discovery(hass: HomeAssistant) -> None:
    """Test config flow: user, but no discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
