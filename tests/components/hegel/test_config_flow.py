"""Test the Hegel config flow."""

from unittest.mock import MagicMock

from homeassistant.components.hegel.const import CONF_MODEL, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import TEST_HOST, TEST_MODEL, TEST_UDN

from tests.common import MockConfigEntry

TEST_NAME = "Hegel H190"
TEST_SSDP_LOCATION = f"http://{TEST_HOST}:8080/description.xml"


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_hegel_client: MagicMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_MODEL: TEST_MODEL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Hegel {TEST_MODEL}"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MODEL: TEST_MODEL,
    }


async def test_user_flow_exception(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_hegel_client: MagicMock,
) -> None:
    """Test user flow when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_hegel_client.ensure_connected.side_effect = OSError("Connection refused")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_MODEL: TEST_MODEL,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_hegel_client.ensure_connected.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_MODEL: TEST_MODEL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_MODEL: TEST_MODEL,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_hegel_client: MagicMock,
) -> None:
    """Test successful SSDP discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
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
        result["flow_id"], {CONF_MODEL: TEST_MODEL}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_MODEL: TEST_MODEL}
    assert result["result"].unique_id == TEST_UDN


async def test_ssdp_discovery_from_ssdp_location(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_hegel_client: MagicMock,
) -> None:
    """Test SSDP discovery extracts host from ssdp_location when presentationURL is not available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={"friendlyName": TEST_NAME, "modelName": TEST_MODEL},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODEL: TEST_MODEL}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_MODEL: TEST_MODEL}


async def test_ssdp_discovery_no_host(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no host can be determined."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
            ssdp_location="",
            upnp={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_found"


async def test_ssdp_discovery_no_udn(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no UDN is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_found"


async def test_ssdp_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test SSDP discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
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


async def test_ssdp_discovery_already_configured_updates_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hegel_client: MagicMock,
) -> None:
    """Test SSDP discovery updates host when device is already configured with different IP."""
    new_host = "192.168.1.50"

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
            ssdp_location=f"http://{new_host}:8080/description.xml",
            upnp={
                "presentationURL": f"http://{new_host}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the host was updated
    assert mock_config_entry.data[CONF_HOST] == new_host


async def test_ssdp_discovery_cannot_connect(
    hass: HomeAssistant,
    mock_hegel_client: MagicMock,
) -> None:
    """Test SSDP discovery aborts when connection fails."""
    mock_hegel_client.ensure_connected.side_effect = OSError("Connection refused")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": TEST_NAME,
                "modelName": TEST_MODEL,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_discovery_unknown_model(
    hass: HomeAssistant,
    mock_hegel_client: MagicMock,
) -> None:
    """Test SSDP discovery with unknown model falls back to first model in list."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_udn=TEST_UDN,
            ssdp_location=TEST_SSDP_LOCATION,
            upnp={
                "presentationURL": f"http://{TEST_HOST}/",
                "friendlyName": "Hegel Unknown",
                "modelName": "UnknownModel",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_ssdp_discovery_multiple_services_same_device(
    hass: HomeAssistant,
    mock_hegel_client: MagicMock,
) -> None:
    """Test that multiple SSDP discoveries from same device result in single discovery.

    A MediaRenderer device advertises multiple SSDP services (RenderingControl,
    AVTransport, ConnectionManager) each with different USN but same UDN.
    This test verifies that only one discovery entry is created.
    """
    # First discovery - RenderingControl service
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
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
        context={"source": SOURCE_SSDP},
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

    # Original flow should still be available
    flows = hass.config_entries.flow.async_progress()
    assert len([f for f in flows if f["flow_id"] == flow_id]) == 1
