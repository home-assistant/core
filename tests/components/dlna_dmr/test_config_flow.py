"""Test the DLNA config flow."""
from __future__ import annotations

from unittest.mock import Mock

from async_upnp_client import UpnpDevice, UpnpError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.dlna_dmr.const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN as DLNA_DOMAIN,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import DiscoveryInfoType

from .conftest import (
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_UDN,
    NEW_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry

# Auto-use the domain_data_mock and dmr_device_mock fixtures for every test in this module
pytestmark = [
    pytest.mark.usefixtures("domain_data_mock"),
    pytest.mark.usefixtures("dmr_device_mock"),
]

WRONG_DEVICE_TYPE = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

IMPORTED_DEVICE_NAME = "Imported DMR device"

MOCK_CONFIG_IMPORT_DATA = {
    CONF_PLATFORM: DLNA_DOMAIN,
    CONF_URL: MOCK_DEVICE_LOCATION,
}

MOCK_ROOT_DEVICE_UDN = "ROOT_DEVICE"

MOCK_DISCOVERY: DiscoveryInfoType = {
    ssdp.ATTR_SSDP_LOCATION: MOCK_DEVICE_LOCATION,
    ssdp.ATTR_SSDP_UDN: MOCK_DEVICE_UDN,
    ssdp.ATTR_SSDP_ST: MOCK_DEVICE_TYPE,
    ssdp.ATTR_UPNP_UDN: MOCK_ROOT_DEVICE_UDN,
    ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
    ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
    ssdp.ATTR_UPNP_SERVICE_LIST: {
        "service": [
            {
                "SCPDURL": "/AVTransport/scpd.xml",
                "controlURL": "/AVTransport/control.xml",
                "eventSubURL": "/AVTransport/event.xml",
                "serviceId": "urn:upnp-org:serviceId:AVTransport",
                "serviceType": "urn:schemas-upnp-org:service:AVTransport:1",
            },
            {
                "SCPDURL": "/ConnectionManager/scpd.xml",
                "controlURL": "/ConnectionManager/control.xml",
                "eventSubURL": "/ConnectionManager/event.xml",
                "serviceId": "urn:upnp-org:serviceId:ConnectionManager",
                "serviceType": "urn:schemas-upnp-org:service:ConnectionManager:1",
            },
            {
                "SCPDURL": "/RenderingControl/scpd.xml",
                "controlURL": "/RenderingControl/control.xml",
                "eventSubURL": "/RenderingControl/event.xml",
                "serviceId": "urn:upnp-org:serviceId:RenderingControl",
                "serviceType": "urn:schemas-upnp-org:service:RenderingControl:1",
            },
        ]
    },
    ssdp.ATTR_HA_MATCHING_DOMAINS: {DLNA_DOMAIN},
}


async def test_user_flow_undiscovered_manual(hass: HomeAssistant) -> None:
    """Test user-init'd flow, no discovered devices, user entering a valid URL."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: MOCK_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {CONF_POLL_AVAILABILITY: True}

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_user_flow_discovered_manual(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test user-init'd flow, with discovered devices, user entering a valid URL."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: MOCK_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {CONF_POLL_AVAILABILITY: True}

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_user_flow_selected(hass: HomeAssistant, ssdp_scanner_mock: Mock) -> None:
    """Test user-init'd flow, user selects discovered device."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MOCK_DEVICE_NAME}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {}

    await hass.async_block_till_done()


async def test_user_flow_uncontactable(
    hass: HomeAssistant, domain_data_mock: Mock
) -> None:
    """Test user-init'd config flow with user entering an uncontactable URL."""
    # Device is not contactable
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: MOCK_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "manual"


async def test_user_flow_embedded_st(
    hass: HomeAssistant, domain_data_mock: Mock
) -> None:
    """Test user-init'd flow for device with an embedded DMR."""
    # Device is the wrong type
    upnp_device = domain_data_mock.upnp_factory.async_create_device.return_value
    upnp_device.udn = MOCK_ROOT_DEVICE_UDN
    upnp_device.device_type = "ROOT_DEVICE_TYPE"
    upnp_device.name = "ROOT_DEVICE_NAME"
    embedded_device = Mock(spec=UpnpDevice)
    embedded_device.udn = MOCK_DEVICE_UDN
    embedded_device.device_type = MOCK_DEVICE_TYPE
    embedded_device.name = MOCK_DEVICE_NAME
    embedded_device.services = upnp_device.services
    upnp_device.services = {}
    upnp_device.all_devices.append(embedded_device)

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: MOCK_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {CONF_POLL_AVAILABILITY: True}

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_user_flow_wrong_st(hass: HomeAssistant, domain_data_mock: Mock) -> None:
    """Test user-init'd config flow with user entering a URL for the wrong device."""
    # Device has a sub device of the right type
    upnp_device = domain_data_mock.upnp_factory.async_create_device.return_value
    upnp_device.device_type = WRONG_DEVICE_TYPE

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: MOCK_DEVICE_LOCATION}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "not_dmr"}
    assert result["step_id"] == "manual"


async def test_import_flow_invalid(hass: HomeAssistant, domain_data_mock: Mock) -> None:
    """Test import flow of invalid YAML config."""
    # Missing CONF_URL
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_PLATFORM: DLNA_DOMAIN},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "incomplete_config"


async def test_import_flow_ssdp_discovered(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test import of YAML config with a device also found via SSDP."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG_IMPORT_DATA,
    )
    await hass.async_block_till_done()

    assert ssdp_scanner_mock.async_get_discovery_info_by_st.call_count >= 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: None,
        CONF_CALLBACK_URL_OVERRIDE: None,
        CONF_POLL_AVAILABILITY: False,
    }

    # The config entry should not be duplicated when dlna_dmr is restarted
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG_IMPORT_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_import_flow_direct_connect(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test import of YAML config with a device *not found* via SSDP."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.return_value = []

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG_IMPORT_DATA,
    )
    await hass.async_block_till_done()

    assert ssdp_scanner_mock.async_get_discovery_info_by_st.call_count >= 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: None,
        CONF_CALLBACK_URL_OVERRIDE: None,
        CONF_POLL_AVAILABILITY: True,
    }

    # The config entry should not be duplicated when dlna_dmr is restarted
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG_IMPORT_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_offline(
    hass: HomeAssistant, domain_data_mock: Mock, ssdp_scanner_mock: Mock
) -> None:
    """Test import flow of offline device."""
    # Device is not yet contactable
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_PLATFORM: DLNA_DOMAIN,
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_NAME: IMPORTED_DEVICE_NAME,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
            CONF_LISTEN_PORT: 2222,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "import_turn_on"

    import_flow_id = result["flow_id"]

    # User clicks submit, same form is displayed with an error
    result = await hass.config_entries.flow.async_configure(
        import_flow_id, user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "import_turn_on"

    # Device is discovered via SSDP, new flow should not be initialized
    ssdp_scanner_mock.async_get_discovery_info_by_st.side_effect = [
        [MOCK_DISCOVERY],
        [],
        [],
    ]
    domain_data_mock.upnp_factory.async_create_device.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"

    # User clicks submit, config entry should be created
    result = await hass.config_entries.flow.async_configure(
        import_flow_id, user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == IMPORTED_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    # Options should be retained
    assert result["options"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_import_flow_options(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test import of YAML config with options set."""
    ssdp_scanner_mock.async_get_discovery_info_by_st.return_value = []

    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_PLATFORM: DLNA_DOMAIN,
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_NAME: IMPORTED_DEVICE_NAME,
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == IMPORTED_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_ssdp_flow_success(hass: HomeAssistant) -> None:
    """Test that SSDP discovery with an available device works."""
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {}


async def test_ssdp_flow_unavailable(
    hass: HomeAssistant, domain_data_mock: Mock
) -> None:
    """Test that SSDP discovery with an unavailable device still succeeds.

    All the required information for configuration is obtained from the SSDP
    message, there's no need to connect to the device to configure it.
    """
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {}


async def test_ssdp_flow_existing(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that SSDP discovery of existing config entry updates the URL."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
            ssdp.ATTR_SSDP_UDN: MOCK_DEVICE_UDN,
            ssdp.ATTR_UPNP_UDN: MOCK_ROOT_DEVICE_UDN,
            ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
            ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == NEW_DEVICE_LOCATION


async def test_ssdp_flow_duplicate_location(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that discovery of device with URL matching existing entry gets aborted."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_DISCOVERY,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == MOCK_DEVICE_LOCATION


async def test_ssdp_flow_upnp_udn(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test that SSDP discovery ignores the root device's UDN."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
            ssdp.ATTR_SSDP_UDN: MOCK_DEVICE_UDN,
            ssdp.ATTR_SSDP_ST: MOCK_DEVICE_TYPE,
            ssdp.ATTR_UPNP_UDN: "DIFFERENT_ROOT_DEVICE",
            ssdp.ATTR_UPNP_DEVICE_TYPE: MOCK_DEVICE_TYPE,
            ssdp.ATTR_UPNP_FRIENDLY_NAME: MOCK_DEVICE_NAME,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_mock.data[CONF_URL] == NEW_DEVICE_LOCATION


async def test_ssdp_missing_services(hass: HomeAssistant) -> None:
    """Test SSDP ignores devices that are missing required services."""
    # No services defined at all
    discovery = dict(MOCK_DISCOVERY)
    del discovery[ssdp.ATTR_UPNP_SERVICE_LIST]
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_dmr"

    # AVTransport service is missing
    discovery = dict(MOCK_DISCOVERY)
    discovery[ssdp.ATTR_UPNP_SERVICE_LIST] = {
        "service": [
            service
            for service in discovery[ssdp.ATTR_UPNP_SERVICE_LIST]["service"]
            if service.get("serviceId") != "urn:upnp-org:serviceId:AVTransport"
        ]
    }
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_dmr"


async def test_ssdp_ignore_device(hass: HomeAssistant) -> None:
    """Test SSDP discovery ignores certain devices."""
    discovery = dict(MOCK_DISCOVERY)
    discovery[ssdp.ATTR_HA_MATCHING_DOMAINS] = {DLNA_DOMAIN, "other_domain"}
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "alternative_integration"

    discovery = dict(MOCK_DISCOVERY)
    discovery[ssdp.ATTR_UPNP_DEVICE_TYPE] = "urn:schemas-upnp-org:device:ZonePlayer:1"
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "alternative_integration"

    for manufacturer, model in [
        ("XBMC Foundation", "Kodi"),
        ("Samsung", "Smart TV"),
        ("LG Electronics.", "LG TV"),
        ("Royal Philips Electronics", "Philips TV DMR"),
    ]:
        discovery = dict(MOCK_DISCOVERY)
        discovery[ssdp.ATTR_UPNP_MANUFACTURER] = manufacturer
        discovery[ssdp.ATTR_UPNP_MODEL_NAME] = model
        result = await hass.config_entries.flow.async_init(
            DLNA_DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "alternative_integration"


async def test_unignore_flow(hass: HomeAssistant, ssdp_scanner_mock: Mock) -> None:
    """Test a config flow started by unignoring a device."""
    # Create ignored entry
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": MOCK_DEVICE_UDN, "title": MOCK_DEVICE_NAME},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {}

    # Device was found via SSDP, matching the 2nd device type tried
    ssdp_scanner_mock.async_get_discovery_info_by_udn_st.side_effect = [
        None,
        MOCK_DISCOVERY,
        None,
        None,
        None,
    ]

    # Unignore it and expect config flow to start
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_UNIGNORE},
        data={"unique_id": MOCK_DEVICE_UDN},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {
        CONF_URL: MOCK_DEVICE_LOCATION,
        CONF_DEVICE_ID: MOCK_DEVICE_UDN,
        CONF_TYPE: MOCK_DEVICE_TYPE,
    }
    assert result["options"] == {}

    # Wait for platform to be fully setup
    await hass.async_block_till_done()


async def test_unignore_flow_offline(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test a config flow started by unignoring a device, but the device is offline."""
    # Create ignored entry
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": MOCK_DEVICE_UDN, "title": MOCK_DEVICE_NAME},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"] == {}

    # Device is not in the SSDP discoveries (perhaps HA restarted between ignore and unignore)
    ssdp_scanner_mock.async_get_discovery_info_by_udn_st.return_value = None

    # Unignore it and expect config flow to start then abort
    result = await hass.config_entries.flow.async_init(
        DLNA_DOMAIN,
        context={"source": config_entries.SOURCE_UNIGNORE},
        data={"unique_id": MOCK_DEVICE_UDN},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "discovery_error"


async def test_options_flow(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test config flow options."""
    config_entry_mock.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry_mock.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    # Invalid URL for callback (can't be validated automatically by voluptuous)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALLBACK_URL_OVERRIDE: "Bad url",
            CONF_POLL_AVAILABILITY: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "invalid_url"}

    # Good data for all fields
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
            CONF_POLL_AVAILABILITY: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_LISTEN_PORT: 2222,
        CONF_CALLBACK_URL_OVERRIDE: "http://override/callback",
        CONF_POLL_AVAILABILITY: True,
    }
