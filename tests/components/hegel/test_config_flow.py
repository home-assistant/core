"""Test the Hegel config flow."""

from unittest.mock import MagicMock

from aiohttp import ClientError

from homeassistant import config_entries
from homeassistant.components.hegel.const import CONF_MODEL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_HOST = "192.168.1.100"
TEST_NAME = "Hegel H190"
TEST_MODEL = "H190"
TEST_UNIQUE_ID = "mac:001122334455"
TEST_MAC = "00:11:22:33:44:55"
TEST_SERIAL = "SN123456789"
TEST_UDN = "uuid:12345678-1234-1234-1234-123456789abc"
TEST_SSDP_LOCATION = f"http://{TEST_HOST}:8080/description.xml"


# SSDP Discovery Tests


async def test_ssdp_discovery_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful SSDP discovery with MAC address."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text=f"""<?xml version="1.0"?>
        <root>
            <device>
                <friendlyName>{TEST_NAME}</friendlyName>
                <modelName>{TEST_MODEL}</modelName>
                <MAC>{TEST_MAC}</MAC>
            </device>
        </root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: TEST_MODEL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_ssdp_discovery_from_ssdp_location(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery extracts host from ssdp_location when presentationURL is not available."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text="""<?xml version="1.0"?>
        <root><device><friendlyName>Hegel</friendlyName></device></root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={"friendlyName": TEST_NAME, "modelName": TEST_MODEL},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_no_host(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no host can be determined."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="",
            upnp={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_found"


async def test_ssdp_discovery_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test SSDP discovery aborts when device is already configured."""
    # The config flow uses ssdp_udn or ssdp_usn as unique_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_usn",
        data={CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME, CONF_MODEL: TEST_MODEL},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery_with_serial_number(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery extracts serial number from device description."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text=f"""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0">
            <device>
                <friendlyName>{TEST_NAME}</friendlyName>
                <modelName>{TEST_MODEL}</modelName>
                <serialNumber>{TEST_SERIAL}</serialNumber>
            </device>
        </root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_with_udn(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery extracts UDN from device description."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text=f"""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0">
            <device>
                <friendlyName>{TEST_NAME}</friendlyName>
                <modelName>{TEST_MODEL}</modelName>
                <UDN>{TEST_UDN}</UDN>
            </device>
        </root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_no_ssdp_location_for_description(
    hass: HomeAssistant, mock_connection_success: MagicMock
) -> None:
    """Test SSDP discovery proceeds without unique_id when ssdp_location is empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="",
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_description_fetch_error(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery proceeds when fetching description.xml fails."""
    aioclient_mock.get(TEST_SSDP_LOCATION, exc=ClientError("Network error"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_invalid_xml(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery proceeds when description.xml is invalid XML."""
    aioclient_mock.get(TEST_SSDP_LOCATION, text="<invalid xml>")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_no_unique_id_info(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery proceeds when description.xml has no MAC, serial, or UDN."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text="""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0">
            <device>
                <friendlyName>Hegel H190</friendlyName>
                <modelName>H190</modelName>
            </device>
        </root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_unknown_model(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test SSDP discovery with unknown model falls back to first model in list."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text="""<?xml version="1.0"?>
        <root><device><friendlyName>Hegel Unknown</friendlyName></device></root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": "Hegel Unknown",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_with_empty_upnp(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test SSDP discovery when upnp data is empty but ssdp_location has host."""
    aioclient_mock.get(
        TEST_SSDP_LOCATION,
        text="""<?xml version="1.0"?>
        <root><device><friendlyName>Hegel</friendlyName></device></root>""",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={},
        ),
    )

    # Host is extracted from ssdp_location, so flow proceeds to discovery_confirm step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_no_host_no_location(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when both upnp and ssdp_location are empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="",
            upnp={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_found"


async def test_ssdp_discovery_multiple_services_same_device(
    hass: HomeAssistant,
    mock_connection_success: MagicMock,
) -> None:
    """Test that multiple SSDP discoveries from same device (different services) result in single discovery.

    A MediaRenderer device advertises multiple SSDP services (RenderingControl,
    AVTransport, ConnectionManager) each with different USN but same UDN.
    This test verifies that only one discovery entry is created.
    """
    # First discovery - RenderingControl service
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn=f"{TEST_UDN}::urn:schemas-upnp-org:service:RenderingControl:1",
            ssdp_st="urn:schemas-upnp-org:service:RenderingControl:1",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "discovery_confirm"
    flow_id = result1["flow_id"]

    # Second discovery - AVTransport service (different USN, same UDN)
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn=f"{TEST_UDN}::urn:schemas-upnp-org:service:AVTransport:1",
            ssdp_st="urn:schemas-upnp-org:service:AVTransport:1",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    # Second discovery should abort since same UDN is already in progress
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    # Third discovery - ConnectionManager service (different USN, same UDN)
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn=f"{TEST_UDN}::urn:schemas-upnp-org:service:ConnectionManager:1",
            ssdp_st="urn:schemas-upnp-org:service:ConnectionManager:1",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    # Third discovery should also abort
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"

    # Original flow should still be available
    flows = hass.config_entries.flow.async_progress()
    assert len([f for f in flows if f["flow_id"] == flow_id]) == 1
