"""Test Axis config flow."""
from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant.components import dhcp, ssdp, zeroconf
from homeassistant.components.axis import config_flow
from homeassistant.components.axis.const import (
    CONF_EVENTS,
    CONF_STREAM_PROFILE,
    CONF_VIDEO_SOURCE,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_VIDEO_SOURCE,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    SOURCE_SSDP,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEFAULT_HOST, MAC, MODEL, NAME

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config_entry")
async def mock_config_entry_fixture(hass, config_entry, mock_setup_entry):
    """Mock config entry and setup entry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_flow_manual_configuration(
    hass: HomeAssistant, setup_default_vapix_requests, mock_setup_entry
) -> None:
    """Test that config flow works."""
    MockConfigEntry(domain=AXIS_DOMAIN, source=SOURCE_IGNORE).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 80,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 0",
    }


async def test_manual_configuration_update_configuration(
    hass: HomeAssistant, mock_config_entry, mock_vapix_requests
) -> None:
    """Test that config flow fails on already configured device."""
    assert mock_config_entry.data[CONF_HOST] == "1.2.3.4"

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_vapix_requests("2.3.4.5")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "2.3.4.5",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 80,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "2.3.4.5"


async def test_flow_fails_faulty_credentials(hass: HomeAssistant) -> None:
    """Test that config flow fails on faulty credentials."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.axis.config_flow.get_axis_device",
        side_effect=config_flow.AuthenticationRequired,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_fails_cannot_connect(hass: HomeAssistant) -> None:
    """Test that config flow fails on cannot connect."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.axis.config_flow.get_axis_device",
        side_effect=config_flow.CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PORT: 80,
            },
        )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_create_entry_multiple_existing_entries_of_same_model(
    hass: HomeAssistant, setup_default_vapix_requests, mock_setup_entry
) -> None:
    """Test that create entry can generate a name with other entries."""
    entry = MockConfigEntry(
        domain=AXIS_DOMAIN,
        data={CONF_NAME: "M1065-LW 0", CONF_MODEL: "M1065-LW"},
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=AXIS_DOMAIN,
        data={CONF_NAME: "M1065-LW 1", CONF_MODEL: "M1065-LW"},
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 80,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 2",
    }

    assert result["data"][CONF_NAME] == "M1065-LW 2"


async def test_reauth_flow_update_configuration(
    hass: HomeAssistant, mock_config_entry, mock_vapix_requests
) -> None:
    """Test that config flow fails on already configured device."""
    assert mock_config_entry.data[CONF_HOST] == "1.2.3.4"
    assert mock_config_entry.data[CONF_USERNAME] == "root"
    assert mock_config_entry.data[CONF_PASSWORD] == "pass"

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        context={"source": SOURCE_REAUTH},
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_vapix_requests("2.3.4.5")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "2.3.4.5",
            CONF_USERNAME: "user2",
            CONF_PASSWORD: "pass2",
            CONF_PORT: 80,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "2.3.4.5"
    assert mock_config_entry.data[CONF_USERNAME] == "user2"
    assert mock_config_entry.data[CONF_PASSWORD] == "pass2"


@pytest.mark.parametrize(
    ("source", "discovery_info"),
    [
        (
            SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                hostname=f"axis-{MAC}",
                ip=DEFAULT_HOST,
                macaddress=MAC,
            ),
        ),
        (
            SOURCE_SSDP,
            ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={
                    "st": "urn:axis-com:service:BasicService:1",
                    "usn": f"uuid:Upnp-BasicDevice-1_0-{MAC}::urn:axis-com:service:BasicService:1",
                    "ext": "",
                    "server": (
                        "Linux/4.14.173-axis8, UPnP/1.0, Portable SDK for UPnP"
                        " devices/1.8.7"
                    ),
                    "deviceType": "urn:schemas-upnp-org:device:Basic:1",
                    "friendlyName": f"AXIS M1065-LW - {MAC}",
                    "manufacturer": "AXIS",
                    "manufacturerURL": "http://www.axis.com/",
                    "modelDescription": "AXIS M1065-LW Network Camera",
                    "modelName": "AXIS M1065-LW",
                    "modelNumber": "M1065-LW",
                    "modelURL": "http://www.axis.com/",
                    "serialNumber": MAC,
                    "UDN": f"uuid:Upnp-BasicDevice-1_0-{MAC}",
                    "serviceList": {
                        "service": {
                            "serviceType": "urn:axis-com:service:BasicService:1",
                            "serviceId": "urn:axis-com:serviceId:BasicServiceId",
                            "controlURL": "/upnp/control/BasicServiceId",
                            "eventSubURL": "/upnp/event/BasicServiceId",
                            "SCPDURL": "/scpd_basic.xml",
                        }
                    },
                    "presentationURL": f"http://{DEFAULT_HOST}:80/",
                },
            ),
        ),
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address(DEFAULT_HOST),
                ip_addresses=[ip_address(DEFAULT_HOST)],
                port=80,
                hostname=f"axis-{MAC.lower()}.local.",
                type="_axis-video._tcp.local.",
                name=f"AXIS M1065-LW - {MAC}._axis-video._tcp.local.",
                properties={
                    "_raw": {"macaddress": MAC.encode()},
                    "macaddress": MAC,
                },
            ),
        ),
    ],
)
async def test_discovery_flow(
    hass: HomeAssistant,
    setup_default_vapix_requests,
    source: str,
    discovery_info: dict,
    mock_setup_entry,
) -> None:
    """Test the different discovery flows for new devices work."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, data=discovery_info, context={"source": source}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0].get("context", {}).get("configuration_url") == "http://1.2.3.4:80"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 80,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"M1065-LW - {MAC}"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MODEL: "M1065-LW",
        CONF_NAME: "M1065-LW 0",
    }

    assert result["data"][CONF_NAME] == "M1065-LW 0"


@pytest.mark.parametrize(
    ("source", "discovery_info"),
    [
        (
            SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                hostname=f"axis-{MAC}",
                ip=DEFAULT_HOST,
                macaddress=MAC,
            ),
        ),
        (
            SOURCE_SSDP,
            ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={
                    "friendlyName": f"AXIS M1065-LW - {MAC}",
                    "serialNumber": MAC,
                    "presentationURL": f"http://{DEFAULT_HOST}:80/",
                },
            ),
        ),
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address(DEFAULT_HOST),
                ip_addresses=[ip_address(DEFAULT_HOST)],
                hostname="mock_hostname",
                name=f"AXIS M1065-LW - {MAC}._axis-video._tcp.local.",
                port=80,
                properties={"macaddress": MAC},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovered_device_already_configured(
    hass: HomeAssistant, mock_config_entry, source: str, discovery_info: dict
) -> None:
    """Test that discovery doesn't setup already configured devices."""
    assert mock_config_entry.data[CONF_HOST] == DEFAULT_HOST

    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, data=discovery_info, context={"source": source}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == DEFAULT_HOST


@pytest.mark.parametrize(
    ("source", "discovery_info", "expected_port"),
    [
        (
            SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                hostname=f"axis-{MAC}",
                ip="2.3.4.5",
                macaddress=MAC,
            ),
            80,
        ),
        (
            SOURCE_SSDP,
            ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={
                    "friendlyName": f"AXIS M1065-LW - {MAC}",
                    "serialNumber": MAC,
                    "presentationURL": "http://2.3.4.5:8080/",
                },
            ),
            8080,
        ),
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("2.3.4.5"),
                ip_addresses=[ip_address("2.3.4.5")],
                hostname="mock_hostname",
                name=f"AXIS M1065-LW - {MAC}._axis-video._tcp.local.",
                port=8080,
                properties={"macaddress": MAC},
                type="mock_type",
            ),
            8080,
        ),
    ],
)
async def test_discovery_flow_updated_configuration(
    hass: HomeAssistant,
    mock_config_entry,
    mock_vapix_requests,
    source: str,
    discovery_info: dict,
    expected_port: int,
) -> None:
    """Test that discovery flow update configuration with new parameters."""
    assert mock_config_entry.data == {
        CONF_HOST: DEFAULT_HOST,
        CONF_PORT: 80,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }

    mock_vapix_requests("2.3.4.5")
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, data=discovery_info, context={"source": source}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "2.3.4.5",
        CONF_PORT: expected_port,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }


@pytest.mark.parametrize(
    ("source", "discovery_info"),
    [
        (
            SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                hostname="",
                ip="",
                macaddress="01234567890",
            ),
        ),
        (
            SOURCE_SSDP,
            ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={
                    "friendlyName": "",
                    "serialNumber": "01234567890",
                    "presentationURL": "",
                },
            ),
        ),
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
                ip_address=None,
                ip_addresses=[],
                hostname="mock_hostname",
                name="",
                port=0,
                properties={"macaddress": "01234567890"},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovery_flow_ignore_non_axis_device(
    hass: HomeAssistant, source: str, discovery_info: dict
) -> None:
    """Test that discovery flow ignores devices with non Axis OUI."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, data=discovery_info, context={"source": source}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_axis_device"


@pytest.mark.parametrize(
    ("source", "discovery_info"),
    [
        (
            SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                hostname=f"axis-{MAC}",
                ip="169.254.3.4",
                macaddress=MAC,
            ),
        ),
        (
            SOURCE_SSDP,
            ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={
                    "friendlyName": f"AXIS M1065-LW - {MAC}",
                    "serialNumber": MAC,
                    "presentationURL": "http://169.254.3.4:80/",
                },
            ),
        ),
        (
            SOURCE_ZEROCONF,
            zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("169.254.3.4"),
                ip_addresses=[ip_address("169.254.3.4")],
                hostname="mock_hostname",
                name=f"AXIS M1065-LW - {MAC}._axis-video._tcp.local.",
                port=80,
                properties={"macaddress": MAC},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovery_flow_ignore_link_local_address(
    hass: HomeAssistant, source: str, discovery_info: dict
) -> None:
    """Test that discovery flow ignores devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        AXIS_DOMAIN, data=discovery_info, context={"source": source}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "link_local_address"


async def test_option_flow(hass: HomeAssistant, setup_config_entry) -> None:
    """Test config flow options."""
    assert CONF_STREAM_PROFILE not in setup_config_entry.options
    assert CONF_VIDEO_SOURCE not in setup_config_entry.options

    result = await hass.config_entries.options.async_init(setup_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_stream"
    assert set(result["data_schema"].schema[CONF_STREAM_PROFILE].container) == {
        DEFAULT_STREAM_PROFILE,
        "profile_1",
        "profile_2",
    }
    assert set(result["data_schema"].schema[CONF_VIDEO_SOURCE].container) == {
        DEFAULT_VIDEO_SOURCE,
        1,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_STREAM_PROFILE: "profile_1", CONF_VIDEO_SOURCE: 1},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_EVENTS: True,
        CONF_STREAM_PROFILE: "profile_1",
        CONF_VIDEO_SOURCE: 1,
    }
    assert setup_config_entry.options[CONF_STREAM_PROFILE] == "profile_1"
    assert setup_config_entry.options[CONF_VIDEO_SOURCE] == 1
