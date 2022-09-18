"""Test the DLNA DMS config flow."""
from __future__ import annotations

from collections.abc import Iterable
import dataclasses
from typing import Final
from unittest.mock import Mock, patch

from async_upnp_client.exceptions import UpnpError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.dlna_dms.const import CONF_SOURCE_ID, DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_URL
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_DEVICE_HOST,
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_UDN,
    MOCK_DEVICE_USN,
    MOCK_SOURCE_ID,
    NEW_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry

WRONG_DEVICE_TYPE: Final = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

MOCK_ROOT_DEVICE_UDN: Final = "ROOT_DEVICE"

MOCK_DISCOVERY: Final = ssdp.SsdpServiceInfo(
    ssdp_usn=MOCK_DEVICE_USN,
    ssdp_location=MOCK_DEVICE_LOCATION,
    ssdp_udn=MOCK_DEVICE_UDN,
    ssdp_st=MOCK_DEVICE_TYPE,
    upnp={
        ssdp.ATTR_UPNP_UDN: MOCK_ROOT_DEVICE_UDN,
        ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
        ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
        ssdp.ATTR_UPNP_SERVICE_LIST: {
            "service": [
                {
                    "SCPDURL": "/ContentDirectory/scpd.xml",
                    "controlURL": "/ContentDirectory/control.xml",
                    "eventSubURL": "/ContentDirectory/event.xml",
                    "serviceId": "urn:upnp-org:serviceId:ContentDirectory",
                    "serviceType": "urn:schemas-upnp-org:service:ContentDirectory:1",
                },
                {
                    "SCPDURL": "/ConnectionManager/scpd.xml",
                    "controlURL": "/ConnectionManager/control.xml",
                    "eventSubURL": "/ConnectionManager/event.xml",
                    "serviceId": "urn:upnp-org:serviceId:ConnectionManager",
                    "serviceType": "urn:schemas-upnp-org:service:ConnectionManager:1",
                },
            ]
        },
    },
    x_homeassistant_matching_domains={DOMAIN},
)


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Iterable[Mock]:
    """Avoid setting up the entire integration."""
    with patch(
        "homeassistant.components.dlna_dms.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


async def test_user_flow(hass: HomeAssistant, ssdp_scanner_mock: Mock) -> None:
    """Test user-init'd flow, user selects discovered device."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
        [],
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MOCK_DEVICE_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_USN,
        CONF_SOURCE_ID: MOCK_SOURCE_ID,
    }
    assert result["options"] == {}


async def test_user_flow_no_devices(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test user-init'd flow, there's really no devices to choose from."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [],
        [],
        [],
        [],
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_ssdp_flow_success(hass: HomeAssistant) -> None:
    """Test that SSDP discovery with an available device works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_USN,
        CONF_SOURCE_ID: MOCK_SOURCE_ID,
    }
    assert result["options"] == {}


async def test_ssdp_flow_unavailable(
    hass: HomeAssistant, upnp_factory_mock: Mock
) -> None:
    """Test that SSDP discovery with an unavailable device still succeeds.

    All the required information for configuration is obtained from the SSDP
    message, there's no need to connect to the device to configure it.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    upnp_factory_mock.async_create_device.side_effect = UpnpError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_USN,
        CONF_SOURCE_ID: MOCK_SOURCE_ID,
    }
    assert result["options"] == {}


async def test_ssdp_flow_existing(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that SSDP discovery of existing config entry updates the URL."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_st="mock_st",
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_udn=MOCK_DEVICE_UDN,
            upnp={
                ssdp.ATTR_UPNP_UDN: MOCK_ROOT_DEVICE_UDN,
                ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
                ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
            },
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == NEW_DEVICE_LOCATION


async def test_ssdp_flow_duplicate_location(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that discovery of device with URL matching existing entry gets aborted."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == MOCK_DEVICE_LOCATION


async def test_ssdp_flow_bad_data(hass: HomeAssistant) -> None:
    """Test bad SSDP discovery information is rejected cleanly."""
    # Missing location
    discovery = dataclasses.replace(MOCK_DISCOVERY, ssdp_location="")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "bad_ssdp"

    # Missing USN
    discovery = dataclasses.replace(MOCK_DISCOVERY, ssdp_usn="")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "bad_ssdp"


async def test_duplicate_name(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test device with name same as other devices results in no error."""
    # Add two entries to test generate_source_id() tries for no collisions
    config_entry_mock.add_to_hass(hass)
    mock_entry_1 = MockConfigEntry(
        unique_id="mock_entry_1",
        domain=DOMAIN,
        data={
            CONF_URL: "not-important",
            CONF_DEVICE_ID: "not-important",
            CONF_SOURCE_ID: f"{MOCK_SOURCE_ID}_1",
        },
        title=MOCK_DEVICE_NAME,
    )
    mock_entry_1.add_to_hass(hass)

    # New UDN, USN, and location to be sure it's a new device
    new_device_udn = "uuid:7bf34520-f034-4fa2-8d2d-2f709d422000"
    new_device_usn = f"{new_device_udn}::{MOCK_DEVICE_TYPE}"
    new_device_location = "http://192.88.99.22/dms_description.xml"
    discovery = dataclasses.replace(
        MOCK_DISCOVERY,
        ssdp_usn=new_device_usn,
        ssdp_location=new_device_location,
        ssdp_udn=new_device_udn,
    )
    discovery.upnp = dict(discovery.upnp)
    discovery.upnp[ssdp.ATTR_UPNP_UDN] = new_device_udn

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: new_device_location,
        CONF_DEVICE_ID: new_device_usn,
        CONF_SOURCE_ID: f"{MOCK_SOURCE_ID}_2",
    }
    assert result["options"] == {}


async def test_ssdp_flow_upnp_udn(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that SSDP discovery ignores the root device's UDN."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={
                ssdp.ATTR_UPNP_UDN: "DIFFERENT_ROOT_DEVICE",
                ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
                ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
            },
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == NEW_DEVICE_LOCATION


async def test_ssdp_missing_services(hass: HomeAssistant) -> None:
    """Test SSDP ignores devices that are missing required services."""
    # No service list at all
    discovery = dataclasses.replace(MOCK_DISCOVERY)
    discovery.upnp = dict(discovery.upnp)
    del discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "not_dms"

    # Service list does not contain services
    discovery = dataclasses.replace(MOCK_DISCOVERY)
    discovery.upnp = dict(discovery.upnp)
    discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST] = {"bad_key": "bad_value"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "not_dms"

    # ContentDirectory service is missing
    discovery = dataclasses.replace(MOCK_DISCOVERY)
    discovery.upnp = dict(discovery.upnp)
    discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST] = {
        "service": [
            service
            for service in discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST]["service"]
            if service.get("serviceId") != "urn:upnp-org:serviceId:ContentDirectory"
        ]
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "not_dms"


async def test_ssdp_single_service(hass: HomeAssistant) -> None:
    """Test SSDP discovery info with only one service defined.

    THe etree_to_dict function turns multiple services into a list of dicts, but
    a single service into only a dict.
    """
    discovery = dataclasses.replace(MOCK_DISCOVERY)
    discovery.upnp = dict(discovery.upnp)
    service_list = dict(discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST])
    # Turn mock's list of service dicts into a single dict
    service_list["service"] = service_list["service"][0]
    discovery.upnp[ssdp.ATTR_UPNP_SERVICE_LIST] = service_list

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "not_dms"
