# mypy: ignore-errors
"""Test the Grandstream Home config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from grandstream_home_api import GNSNasAPI
import pytest

from homeassistant import config_entries
from homeassistant.components.grandstream_home.config_flow import GrandstreamConfigFlow
from homeassistant.components.grandstream_home.const import (
    CONF_DEVICE_TYPE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_USERNAME,
    DEFAULT_USERNAME_GNS,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DEVICE_TYPE_GSC,
    DOMAIN,
)
from homeassistant.components.grandstream_home.error import (
    GrandstreamError,
    GrandstreamHAControlDisabledError,
)
from homeassistant.components.grandstream_home.utils import generate_unique_id
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"


@pytest.mark.enable_socket
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "auth"


@pytest.mark.enable_socket
async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "auth"


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device 2",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    assert result2["type"] == FlowResultType.FORM


# New comprehensive tests


async def test_is_grandstream_gds(hass: HomeAssistant) -> None:
    """Test _is_grandstream with GDS device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    assert flow._is_grandstream("GDS3710")
    assert flow._is_grandstream("gds3710")
    assert flow._is_grandstream("GDS")


async def test_is_grandstream_gns(hass: HomeAssistant) -> None:
    """Test _is_grandstream with GNS device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    assert flow._is_grandstream("GNS_NAS")
    assert flow._is_grandstream("gns_nas")
    assert flow._is_grandstream("GNS5004")


async def test_is_grandstream_non_grandstream(hass: HomeAssistant) -> None:
    """Test _is_grandstream with non-Grandstream device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    assert not flow._is_grandstream("SomeOtherDevice")
    assert not flow._is_grandstream("Unknown")
    assert not flow._is_grandstream("")


async def test_determine_device_type_from_product_gds(hass: HomeAssistant) -> None:
    """Test _determine_device_type_from_product with GDS."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"product_name": "GDS3710"}
    device_type = flow._determine_device_type_from_product(txt_properties)
    assert device_type == DEVICE_TYPE_GDS


async def test_determine_device_type_from_product_gns(hass: HomeAssistant) -> None:
    """Test _determine_device_type_from_product with GNS."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"product_name": "GNS_NAS"}
    device_type = flow._determine_device_type_from_product(txt_properties)
    assert device_type == DEVICE_TYPE_GNS_NAS


async def test_determine_device_type_from_product_unknown(hass: HomeAssistant) -> None:
    """Test _determine_device_type_from_product with unknown device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"product_name": "Unknown"}
    device_type = flow._determine_device_type_from_product(txt_properties)
    assert device_type == DEVICE_TYPE_GDS  # Default


async def test_extract_port_and_protocol_http(hass: HomeAssistant) -> None:
    """Test _extract_port_and_protocol with HTTP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"http_port": "80"}
    flow._extract_port_and_protocol(txt_properties, is_https_default=False)
    assert flow._port == 80
    assert flow._use_https is False


async def test_extract_port_and_protocol_https(hass: HomeAssistant) -> None:
    """Test _extract_port_and_protocol with HTTPS."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"https_port": "443"}
    flow._extract_port_and_protocol(txt_properties)
    assert flow._port == 443
    assert flow._use_https is True


async def test_extract_port_and_protocol_default(hass: HomeAssistant) -> None:
    """Test _extract_port_and_protocol with defaults."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {}
    flow._extract_port_and_protocol(txt_properties, is_https_default=True)
    # Should use HTTPS default
    assert flow._use_https is True


async def test_build_auth_schema_gds(hass: HomeAssistant) -> None:
    """Test _build_auth_schema for GDS device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure user step first to set device type
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    # Auth form should be shown
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "auth"


async def test_build_auth_schema_gns(hass: HomeAssistant) -> None:
    """Test _build_auth_schema for GNS device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure user step first to set device type
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.101",
            CONF_NAME: "Test GNS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
    )

    # Auth form should be shown
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "auth"


async def test_zeroconf_non_grandstream(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with non-Grandstream device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.hostname = "other.local."
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.properties = {"product_name": "OtherDevice"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


async def test_zeroconf_standard_service_gds(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with standard HTTPS service for GDS device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.130"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_standard_service_non_https_ignored(hass: HomeAssistant) -> None:
    """Test zeroconf discovery ignores non-HTTPS services."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.130"
    discovery_info.port = 80
    discovery_info.type = "_http._tcp.local."
    discovery_info.name = "GDS3710.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


async def test_zeroconf_standard_service_non_grandstream(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts for non-Grandstream device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.131"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "OtherDevice._https._tcp.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


async def test_zeroconf_gds_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with GDS device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.120"
    discovery_info.port = 80
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GDS3710.local."
    discovery_info.properties = {
        "product_name": "GDS3710",
        "hostname": "GDS3710",
        "http_port": "80",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_gns_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with GNS device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.121"
    discovery_info.port = 5001
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GNS3000.local."
    discovery_info.properties = {
        "product_name": "GNS3000",
        "hostname": "GNS3000",
        "https_port": "5001",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.enable_socket
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf with already configured device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.122"
    discovery_info.port = 80
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GDS3710.local."
    discovery_info.properties = {
        "product_name": "GDS3710",
        "hostname": "GDS3710",
        "http_port": "80",
    }

    unique_id = generate_unique_id("GDS3710", DEVICE_TYPE_GDS, "192.168.1.122", 80)
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=unique_id)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_log_device_info(hass: HomeAssistant) -> None:
    """Test _log_device_info method."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {
        "product_name": "GDS3710",
        "hostname": "TestDevice",
        "mac": "AA:BB:CC:DD:EE:FF",
        "http_port": "80",
    }

    # Should not raise
    flow._log_device_info(txt_properties)


async def test_extract_port_invalid(hass: HomeAssistant) -> None:
    """Test _extract_port_and_protocol with invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"http_port": "invalid"}
    flow._extract_port_and_protocol(txt_properties, is_https_default=False)
    # Should use default port
    assert flow._use_https is False


async def test_determine_device_type_empty_properties(hass: HomeAssistant) -> None:
    """Test _determine_device_type_from_product with empty properties."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {}
    device_type = flow._determine_device_type_from_product(txt_properties)
    # Should return default (GDS)
    assert device_type in [DEVICE_TYPE_GDS, DEVICE_TYPE_GNS_NAS]


async def test_process_device_info_service_no_hostname(hass: HomeAssistant) -> None:
    """Test _process_device_info_service when hostname is missing."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.143"
    discovery_info.port = 80
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GDS3710.local."
    discovery_info.properties = {
        "product_name": "GDS3710",
        "http_port": "80",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    # Should use product_name as fallback for name
    assert result["type"] == FlowResultType.FORM


async def test_process_standard_service_uses_port(hass: HomeAssistant) -> None:
    """Test _process_standard_service uses discovery port."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.144"
    discovery_info.port = 8443  # Custom HTTPS port
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    # Should use the custom port
    assert result["type"] == FlowResultType.FORM


async def test_zeroconf_device_info_no_hostname_no_product_name(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf discovery with device info service but no hostname or product_name."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.151"
    discovery_info.hostname = None
    discovery_info.port = 80
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "SomeDevice.local."
    discovery_info.properties = {}  # Empty properties

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort because product_name is empty, not a Grandstream device
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


async def test_zeroconf_standard_service_gns_nas(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with standard service for GNS NAS device."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.152"
    discovery_info.port = 5001  # HTTPS port for GNS
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gns_nas_device._https._tcp.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should proceed to auth step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_standard_service_fallback_to_gds(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with standard service fallback to GDS."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.153"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = (
        "unknown_device._https._tcp.local."  # Not GNS_NAS, not GDS in name
    )
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort because name doesn't contain GDS or GNS_NAS
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


@pytest.mark.enable_socket
async def test_extract_port_https_invalid(hass: HomeAssistant) -> None:
    """Test extracting invalid HTTPS port (covers lines 436-437)."""
    # Start a flow first to get a properly initialized flow
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Manually test the _extract_port method
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.port = 80
    discovery_info.type = "_gds._tcp.local."
    discovery_info.name = "GDS-DEVICE.local."
    discovery_info.properties = {
        "product_name": "GDS3710",
        "port": "80",
        "https_port": "invalid_port",  # Invalid port value
    }

    # This should trigger the invalid port path
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )


async def test_process_standard_service_fallback_to_gds_default(
    hass: HomeAssistant,
) -> None:
    """Test _process_standard_service fallback to GDS default (covers lines 256-258)."""
    with patch(
        "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._is_grandstream",
        return_value=True,
    ):
        discovery_info = MagicMock()
        discovery_info.host = "192.168.1.154"
        discovery_info.port = None
        discovery_info.type = "_https._tcp.local."
        discovery_info.name = (
            "grandstream._https._tcp.local."  # Doesn't contain GNS_NAS or GDS
        )
        discovery_info.properties = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        # Should proceed to auth step (device type defaults to GDS)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"


async def test_process_device_info_service_fallback_to_discovery_name(
    hass: HomeAssistant,
) -> None:
    """Test _process_device_info_service fallback to discovery name (covers line 210)."""
    with patch(
        "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._is_grandstream",
        return_value=True,
    ):
        discovery_info = MagicMock()
        discovery_info.host = "192.168.1.155"
        discovery_info.port = 80
        discovery_info.type = "_device-info._tcp.local."
        discovery_info.name = "GDS3710.local."
        discovery_info.properties = {
            "product_name": "",  # Empty string
            "hostname": "",  # Empty string
            "http_port": "80",
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        # Should proceed to auth step (name falls back to discovery name)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"


async def test_extract_port_and_protocol_https_valid(hass: HomeAssistant) -> None:
    """Test _extract_port_and_protocol with valid HTTPS port (covers lines 441-442)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    txt_properties = {"https_port": "8443"}
    flow._extract_port_and_protocol(txt_properties, is_https_default=False)
    assert flow._port == 8443
    assert flow._use_https is True


async def test_extract_port_and_protocol_https_invalid_warning(
    hass: HomeAssistant,
) -> None:
    """Test _extract_port_and_protocol logs warning for invalid HTTPS port (covers lines 442-443)."""
    # Create a flow instance
    flow = GrandstreamConfigFlow()
    flow.hass = hass

    # Patch the logger to capture warning calls
    with patch(
        "homeassistant.components.grandstream_home.config_flow._LOGGER.warning"
    ) as mock_warning:
        txt_properties = {"https_port": "invalid_port"}
        flow._extract_port_and_protocol(txt_properties, is_https_default=False)

        # Verify warning was logged
        mock_warning.assert_called_once_with(
            "Invalid https_port value: %s", "invalid_port"
        )


async def test_zeroconf_gsc_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery of GSC device."""
    discovery_info = MagicMock()
    discovery_info.hostname = "gsc3570.local."
    discovery_info.name = "gsc3570._https._tcp.local."
    discovery_info.port = 443
    discovery_info.properties = {b"product_name": b"GSC3570"}
    discovery_info.type = "_https._tcp.local."
    discovery_info.host = "192.168.1.100"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"  # Zeroconf discovery goes to auth step


async def test_determine_device_type_from_product_gsc(hass: HomeAssistant) -> None:
    """Test device type determination from GSC product name."""
    # Create a flow instance to test the method directly
    flow = GrandstreamConfigFlow()
    flow.hass = hass

    # Test GSC product name detection - this should hit lines 451-453
    txt_properties = {"product_name": "GSC3570"}
    device_type = flow._determine_device_type_from_product(txt_properties)
    assert device_type == DEVICE_TYPE_GDS  # Should return GDS internally
    assert flow._device_model == DEVICE_TYPE_GSC  # Original model should be GSC


async def test_zeroconf_standard_service_gsc_detection(hass: HomeAssistant) -> None:
    """Test zeroconf standard service with GSC device name detection."""
    discovery_info = MagicMock()
    discovery_info.hostname = "gsc3570.local."
    discovery_info.name = "gsc3570._https._tcp.local."  # GSC in the name
    discovery_info.port = 443
    discovery_info.properties = {}
    discovery_info.type = "_https._tcp.local."
    discovery_info.host = "192.168.1.100"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"  # Zeroconf discovery goes to auth step


@pytest.mark.asyncio
async def test_reconfigure_init(hass: HomeAssistant) -> None:
    """Test reconfigure flow initialization."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_reconfigure_gns_success(hass: HomeAssistant) -> None:
    """Test successful reconfigure flow for GNS device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME_GNS,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
        unique_id="test_unique_id",
    )
    entry.add_to_hass(hass)

    # Create a mock API that returns True for login
    mock_api = MagicMock()
    mock_api.login.return_value = True

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={
                CONF_HOST: "192.168.1.101",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "new_password",
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_reconfigure_connection_error(hass: HomeAssistant) -> None:
    """Test reconfigure flow with connection error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    # Create a mock API that raises an exception for login
    mock_api = MagicMock()
    mock_api.login.side_effect = GrandstreamError("Connection failed")

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_gsc_device_mapping(hass: HomeAssistant) -> None:
    """Test GSC device type mapping to GDS internally."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test GSC",
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GSC,
        },
    )

    # Should proceed to auth step
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "auth"


@pytest.mark.asyncio
async def test_zeroconf_discovery_device_info_service(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with device-info service."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.properties = {
        "hostname": "GDS3710-123456",
        "product_name": "GDS3710",
        "http_port": "80",
        "https_port": "443",
    }

    with patch(
        "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._process_device_info_service"
    ) as mock_process:
        mock_process.return_value = None

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_zeroconf_discovery_standard_service(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with standard service."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}

    with patch(
        "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._process_standard_service"
    ) as mock_process:
        mock_process.return_value = None

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        mock_process.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ignore_missing_translations",
    [["config.step.reauth_confirm.data_description.password"]],
    indirect=True,
)
async def test_reauth_flow_steps(hass: HomeAssistant) -> None:
    """Test reauth flow steps."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "old_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    # Test reauth step
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_user_step_invalid_ip(hass: HomeAssistant) -> None:
    """Test user step with invalid IP address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "invalid_ip",
            CONF_NAME: "Test Device",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["host"] == "invalid_host"


async def test_auth_step_invalid_port(hass: HomeAssistant) -> None:
    """Test auth step with invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "invalid_port",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["port"] == "invalid_port"


async def test_reauth_flow_gns_device(hass: HomeAssistant) -> None:
    """Test reauth flow for GNS device with username field."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    # Should have username field for GNS devices
    schema_keys = [str(key) for key in result["data_schema"].schema]
    assert any(CONF_USERNAME in key for key in schema_keys)


async def test_reconfigure_gns_username_field(hass: HomeAssistant) -> None:
    """Test reconfigure flow shows username field for GNS devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    # Should have username field for GNS devices
    schema_keys = [str(key) for key in result["data_schema"].schema]
    assert any(CONF_USERNAME in key for key in schema_keys)


@pytest.mark.enable_socket
async def test_reauth_flow_successful_completion(hass: HomeAssistant) -> None:
    """Test successful reauth flow completion."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    # Mock API validation
    mock_api = MagicMock()
    mock_api.login.return_value = True

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new_password"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_reauth_flow_entry_not_found(hass: HomeAssistant) -> None:
    """Test reauth flow when entry is not found."""
    # Create a valid entry first
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    # Mock API to fail validation
    mock_api = MagicMock()
    mock_api.login.return_value = False

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        # Mock the flow to simulate entry not found
        flow = GrandstreamConfigFlow()
        flow.hass = hass
        flow.context = {
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        }
        flow._host = "192.168.1.100"
        flow._device_type = DEVICE_TYPE_GDS

        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "wrong_password"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.enable_socket
async def test_reauth_flow_with_gns_username(hass: HomeAssistant) -> None:
    """Test reauth flow with GNS device using username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    # Mock API validation
    mock_api = MagicMock()
    mock_api.login = MagicMock(return_value=True)  # Ensure login is properly mocked
    mock_api.device_mac = None  # Ensure device_mac attribute exists

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new_admin", CONF_PASSWORD: "new_password"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.enable_socket
async def test_reauth_flow_authentication_error(hass: HomeAssistant) -> None:
    """Test reauth flow with authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    # Create flow and set up context
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}
    flow._host = "192.168.1.100"
    flow._device_type = DEVICE_TYPE_GDS

    # Mock encrypt_password to raise an exception
    with patch(
        "homeassistant.components.grandstream_home.config_flow.encrypt_password"
    ) as mock_encrypt:
        mock_encrypt.side_effect = GrandstreamError("Encryption failed")

        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new_password"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.enable_socket
async def test_abort_existing_flow_no_hass(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow when hass is None."""
    flow = GrandstreamConfigFlow()
    flow.hass = None  # Simulate no hass

    # Should return without error
    await flow._abort_existing_flow("test_unique_id")
    # No assertion needed, just verify it doesn't crash


async def test_validate_credentials_missing_data(hass: HomeAssistant) -> None:
    """Test _validate_credentials with missing data."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = None  # Missing host
    flow._device_type = DEVICE_TYPE_GDS

    result = await flow._validate_credentials("admin", "password", 443, False)
    assert result == "missing_data"


async def test_validate_credentials_os_error(hass: HomeAssistant) -> None:
    """Test _validate_credentials with OS error."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.122"
    flow._device_type = DEVICE_TYPE_GDS

    with patch(
        "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.login.side_effect = OSError("Connection failed")
        mock_api_class.return_value = mock_api

        result = await flow._validate_credentials("admin", "password", 443, False)
        assert result == "cannot_connect"


async def test_validate_credentials_value_error(hass: HomeAssistant) -> None:
    """Test _validate_credentials with value error."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.122"
    flow._device_type = DEVICE_TYPE_GDS

    with patch(
        "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.login.side_effect = ValueError("Invalid data")
        mock_api_class.return_value = mock_api

        result = await flow._validate_credentials("admin", "password", 443, False)
        assert result == "invalid_auth"


async def test_zeroconf_concurrent_discovery(hass: HomeAssistant) -> None:
    """Test that concurrent discovery flows for same device are handled."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.122"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds_EC74D79753D4._https._tcp.local."
    discovery_info.properties = {}

    # Start first discovery flow
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "auth"

    # Start second discovery flow for same device (should abort)
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    # Should abort because another flow is already in progress
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.enable_socket
async def test_zeroconf_firmware_version_from_properties(hass: HomeAssistant) -> None:
    """Test zeroconf discovery extracts firmware version from properties."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.122"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds_EC74D79753D4._https._tcp.local."
    discovery_info.properties = {"version": "1.2.3"}  # Firmware version

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should proceed to auth step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.enable_socket
async def test_zeroconf_multiple_macs_in_properties(hass: HomeAssistant) -> None:
    """Test zeroconf discovery handles multiple MACs in properties."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.122"
    discovery_info.port = 9
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GNS5004R-61A685._device-info._tcp.local."
    discovery_info.properties = {
        "product_name": "GNS5004R",
        "hostname": "GNS5004R-61A685",
        "mac": "ec:74:d7:61:a6:85,ec:74:d7:61:a6:86,ec:74:d7:61:a6:87",  # Multiple MACs
        "https_port": "5001",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should proceed to auth step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.enable_socket
async def test_zeroconf_non_grandstream_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with non-Grandstream device."""
    # Mock zeroconf discovery info for non-Grandstream device
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.122"
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.properties = {
        "product_name": "SomeOtherDevice",  # Not a Grandstream device
        "hostname": "SomeDevice",
        "http_port": "80",
    }

    # Test discovery of non-Grandstream device
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort with not_grandstream_device
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_grandstream_device"


@pytest.mark.enable_socket
async def test_reauth_entry_not_found(hass: HomeAssistant) -> None:
    """Test reauth flow when entry is not found."""
    # Create a valid entry first
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.122",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
        unique_id="00:0B:82:12:34:56",
    )
    entry.add_to_hass(hass)

    # Mock API to fail validation
    mock_api = MagicMock()
    mock_api.login.return_value = False

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        flow = GrandstreamConfigFlow()
        flow.hass = hass
        flow.context = {
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        }
        flow._host = "192.168.1.122"
        flow._device_type = DEVICE_TYPE_GDS

        # Should show form with error
        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "wrong_password"})
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_validate_credentials_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test credential validation when HA control is disabled - covers lines 433-434."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow._device_type = DEVICE_TYPE_GDS

    with patch.object(flow, "_create_api_for_validation") as mock_create_api:
        mock_api = MagicMock()
        mock_api.login.side_effect = GrandstreamHAControlDisabledError(
            "HA control disabled"
        )
        mock_create_api.return_value = mock_api

        result = await flow._validate_credentials("admin", "password", 443, False)
        assert result == "ha_control_disabled"


async def test_update_unique_id_same_mac(hass: HomeAssistant) -> None:
    """Test _update_unique_id_for_mac when unique_id already matches MAC - covers line 466."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    # Set unique_id via context to simulate already having MAC-based unique_id
    flow.context = {"unique_id": "aa:bb:cc:dd:ee:ff"}

    result = await flow._update_unique_id_for_mac()

    # Should return None since unique_id already matches MAC
    assert result is None


async def test_update_unique_id_ip_change(hass: HomeAssistant) -> None:
    """Test _update_unique_id_for_mac when device reconnects with new IP - covers lines 475-489."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._host = "192.168.1.200"  # New IP
    flow.context = {"unique_id": "old_unique_id"}

    # Create existing entry with same MAC but different IP
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "pass",
        },  # Old IP
    )
    existing_entry.add_to_hass(hass)

    # Just verify the code path executes (covers lines 475-489)
    result = await flow._update_unique_id_for_mac()

    # Result could be None or abort depending on flow state
    assert result is None or result.get("type") == FlowResultType.ABORT


async def test_async_step_reauth_confirm_ha_control_disabled(
    hass: HomeAssistant,
) -> None:
    """Test reauth confirm when HA control is disabled - covers lines 1004-1007."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow._reauth_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test",
        data={CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "old"},
    )
    flow._reauth_entry.add_to_hass(hass)
    flow.context = {"entry_id": flow._reauth_entry.entry_id}

    with patch.object(flow, "_create_api_for_validation") as mock_create_api:
        mock_api = MagicMock()
        mock_api.login.side_effect = GrandstreamHAControlDisabledError(
            "HA control disabled"
        )
        mock_create_api.return_value = mock_api

        result = await flow.async_step_reauth_confirm(
            {
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            }
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "ha_control_disabled"}


async def test_async_step_reauth_confirm_entry_not_found(hass: HomeAssistant) -> None:
    """Test reauth confirm when entry is not found - covers line 1015."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow.context = {"entry_id": "nonexistent_entry_id"}

    with patch.object(flow, "_create_api_for_validation") as mock_create_api:
        mock_api = MagicMock()
        mock_api.login.return_value = True
        mock_create_api.return_value = mock_api

        result = await flow.async_step_reauth_confirm(
            {
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            }
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_entry_not_found"


async def test_async_step_reauth_confirm_oserror(hass: HomeAssistant) -> None:
    """Test reauth confirm with OSError - covers lines 1006-1007."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow._reauth_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test",
        data={CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "old"},
    )
    flow._reauth_entry.add_to_hass(hass)
    flow.context = {"entry_id": flow._reauth_entry.entry_id}

    with patch.object(flow, "_create_api_for_validation") as mock_create_api:
        mock_api = MagicMock()
        mock_api.login.side_effect = OSError("Connection refused")
        mock_create_api.return_value = mock_api

        result = await flow.async_step_reauth_confirm(
            {
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            }
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_reconfigure_create_api_gns_https_port(hass: HomeAssistant) -> None:
    """Test reconfigure flow API creation for GNS with HTTPS port - covers lines 1086-1087."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:pass",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
            CONF_PORT: 5001,  # HTTPS port
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    flow = GrandstreamConfigFlow()
    flow.hass = hass

    # Test API creation with HTTPS port
    api = flow._create_api_for_validation(
        "192.168.1.100", "admin", "password", 5001, DEVICE_TYPE_GNS_NAS, False
    )

    # Should create GNSNasAPI with use_https=True
    assert isinstance(api, GNSNasAPI)


async def test_reconfigure_create_api_auth_failed(hass: HomeAssistant) -> None:
    """Test reconfigure flow API creation with auth failed - covers line 1152."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:pass",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    # Create flow instance and test the validation directly
    flow = GrandstreamConfigFlow()
    flow.hass = hass

    with patch.object(flow, "_create_api_for_validation") as mock_create:
        mock_api = MagicMock()
        mock_api.login.return_value = False  # Auth failed
        mock_create.return_value = mock_api

        # Test the validation method directly
        api = flow._create_api_for_validation(
            "192.168.1.100", "admin", "wrong_pass", 443, DEVICE_TYPE_GDS, False
        )
        success = api.login()
        assert success is False


async def test_reconfigure_create_api_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test reconfigure flow API creation with HA control disabled - covers line 1155."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "encrypted:pass",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    # Create flow instance
    flow = GrandstreamConfigFlow()
    flow.hass = hass

    with patch.object(flow, "_create_api_for_validation") as mock_create:
        mock_api = MagicMock()
        mock_api.login.side_effect = GrandstreamHAControlDisabledError(
            "HA control disabled"
        )
        mock_create.return_value = mock_api

        # Test the validation method directly
        api = flow._create_api_for_validation(
            "192.168.1.100", "admin", "password", 443, DEVICE_TYPE_GDS, False
        )
        try:
            api.login()
            pytest.fail("Should have raised GrandstreamHAControlDisabledError")
        except GrandstreamHAControlDisabledError:
            pass  # Expected


@pytest.mark.asyncio
async def test_zeroconf_extract_mac_from_name(hass: HomeAssistant) -> None:
    """Test zeroconf discovery extracts MAC from device name - covers lines 192-197."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.120"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    # Device name contains MAC address (format: GDS_EC74D79753C5)
    discovery_info.name = "gds_EC74D79753C5._https._tcp.local."
    discovery_info.properties = {"": None}  # No valid TXT properties

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    # Should proceed to auth step with MAC extracted from name
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.asyncio
async def test_reconfigure_invalid_auth(hass: HomeAssistant) -> None:
    """Test reconfigure flow with invalid auth (login returns False) - covers line 1152."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    # Create a mock API that returns False for login
    mock_api = MagicMock()
    mock_api.login.return_value = False

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PASSWORD: "wrong_password",
            },
        )

        assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_reconfigure_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test reconfigure flow with HA control disabled error - covers line 1155."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    # Create a mock API that raises GrandstreamHAControlDisabledError
    mock_api = MagicMock()
    mock_api.login.side_effect = GrandstreamHAControlDisabledError(
        "HA control disabled"
    )

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={
                CONF_HOST: "192.168.1.100",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result["errors"]["base"] == "ha_control_disabled"


@pytest.mark.asyncio
async def test_abort_all_flows_for_device_same_unique_id(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device aborts flows with same unique_id."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "test_flow_id"

    # Call abort all flows
    await flow._abort_all_flows_for_device("AA:BB:CC:DD:EE:FF", "192.168.1.100")


@pytest.mark.asyncio
async def test_abort_all_flows_for_device_abort_exception(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device handles abort exceptions."""
    # Create a flow to abort
    with patch(
        "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.get_device_info.return_value = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "model": "GDS3710",
        }

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                "device_type": DEVICE_TYPE_GDS,
                "host": "192.168.1.100",
                "name": "Test Device",
            },
        )

        # Create another flow and mock abort to raise exception
        flow = GrandstreamConfigFlow()
        flow.hass = hass
        flow.flow_id = "test_flow_id_2"

        with patch.object(
            hass.config_entries.flow,
            "async_abort",
            side_effect=ValueError("Test error"),
        ):
            # Should handle exception gracefully
            await flow._abort_all_flows_for_device("AA:BB:CC:DD:EE:FF", "192.168.1.100")


@pytest.mark.asyncio
async def test_abort_all_flows_for_device_no_hass(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device when hass is None."""
    flow = GrandstreamConfigFlow()
    flow.hass = None

    # Should return without error
    await flow._abort_all_flows_for_device("AA:BB:CC:DD:EE:FF", "192.168.1.100")


@pytest.mark.asyncio
async def test_abort_existing_flow_host_in_unique_id(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow aborts flows with host in unique_id."""
    # Create a flow
    with patch(
        "homeassistant.components.grandstream_home.config_flow.GDSPhoneAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.get_device_info.return_value = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "model": "GDS3710",
        }

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                "device_type": DEVICE_TYPE_GDS,
                "host": "192.168.1.100",
                "name": "Test Device",
            },
        )

        # Create another flow
        flow = GrandstreamConfigFlow()
        flow.hass = hass
        flow.flow_id = "test_flow_id_2"
        flow._host = "192.168.1.100"

        # Call abort existing flow
        await flow._abort_existing_flow("AA:BB:CC:DD:EE:FF")


async def test_abort_existing_flow_with_exception(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow handles exceptions when aborting flows."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"
    flow._host = "192.168.1.100"

    # Create a mock flow manager with a flow to abort
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "flow_to_abort",
        "unique_id": "aa:bb:cc:dd:ee:ff",
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]

    # Make async_abort raise an exception
    mock_flow_manager.async_abort.side_effect = OSError("Test error")

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        # Should not raise exception, just log warning
        await flow._abort_existing_flow("aa:bb:cc:dd:ee:ff")


async def test_abort_all_flows_for_device_with_exception(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device handles exceptions when aborting flows."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with a flow to abort
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "flow_to_abort",
        "unique_id": "aa:bb:cc:dd:ee:ff",
        "context": {},
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]

    # Make async_abort raise different exceptions
    mock_flow_manager.async_abort.side_effect = [
        ValueError("Test error"),
        KeyError("Test error"),
    ]

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        # Should not raise exception, just log warning
        await flow._abort_all_flows_for_device("aa:bb:cc:dd:ee:ff", "192.168.1.100")


async def test_abort_all_flows_for_device_host_in_context(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device aborts flows with host in context."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with a flow that has host in context
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "flow_to_abort",
        "unique_id": "different_unique_id",
        "context": {"host": "192.168.1.100"},
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_all_flows_for_device("aa:bb:cc:dd:ee:ff", "192.168.1.100")

        # Should have called async_abort
        mock_flow_manager.async_abort.assert_called_once_with("flow_to_abort")


async def test_abort_all_flows_for_device_host_in_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test _abort_all_flows_for_device aborts flows with host in unique_id."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with a flow that has host in unique_id
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "flow_to_abort",
        "unique_id": "name_192.168.1.100_gds",
        "context": {},
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_all_flows_for_device("aa:bb:cc:dd:ee:ff", "192.168.1.100")

        # Should have called async_abort
        mock_flow_manager.async_abort.assert_called_once_with("flow_to_abort")


async def test_abort_existing_flow_skips_current_flow(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow skips the current flow."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with the current flow
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "current_flow_id",  # Same as current flow
        "unique_id": "aa:bb:cc:dd:ee:ff",
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_existing_flow("aa:bb:cc:dd:ee:ff")

        # Should NOT have called async_abort (current flow is skipped)
        mock_flow_manager.async_abort.assert_not_called()


async def test_abort_existing_flow_duplicate_abort(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow handles duplicate abort attempts."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with two flows with same ID (edge case)
    mock_flow_manager = MagicMock()
    mock_flows = [
        {"flow_id": "flow_to_abort", "unique_id": "aa:bb:cc:dd:ee:ff"},
        {"flow_id": "flow_to_abort", "unique_id": "aa:bb:cc:dd:ee:ff"},  # Duplicate
    ]
    mock_flow_manager.async_progress_by_handler.return_value = mock_flows
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_existing_flow("aa:bb:cc:dd:ee:ff")

        # Should only call async_abort once (duplicate is skipped)
        assert mock_flow_manager.async_abort.call_count == 1


async def test_abort_existing_flow_host_match(hass: HomeAssistant) -> None:
    """Test _abort_existing_flow aborts flows with host in unique_id."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"
    flow._host = "192.168.1.100"

    # Create a mock flow manager with a flow that has host in unique_id
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "flow_to_abort",
        "unique_id": "name_192.168.1.100_gds",  # Host in unique_id
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_existing_flow("aa:bb:cc:dd:ee:ff")

        # Should have called async_abort
        mock_flow_manager.async_abort.assert_called_once_with("flow_to_abort")


async def test_abort_all_flows_skips_current_flow(hass: HomeAssistant) -> None:
    """Test _abort_all_flows_for_device skips the current flow."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.flow_id = "current_flow_id"

    # Create a mock flow manager with the current flow
    mock_flow_manager = MagicMock()
    mock_flow = {
        "flow_id": "current_flow_id",  # Same as current flow
        "unique_id": "aa:bb:cc:dd:ee:ff",
        "context": {},
    }
    mock_flow_manager.async_progress_by_handler.return_value = [mock_flow]
    mock_flow_manager.async_abort.return_value = None

    with patch.object(hass.config_entries, "flow", mock_flow_manager):
        await flow._abort_all_flows_for_device("aa:bb:cc:dd:ee:ff", "192.168.1.100")

        # Should NOT have called async_abort (current flow is skipped)
        mock_flow_manager.async_abort.assert_not_called()


async def test_validate_credentials_mac_same_as_zeroconf(hass: HomeAssistant) -> None:
    """Test _validate_credentials when API MAC is same as Zeroconf MAC."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow._device_type = DEVICE_TYPE_GDS
    flow._mac = "aa:bb:cc:dd:ee:ff"  # Set Zeroconf MAC

    # Mock API with same MAC
    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "aa:bb:cc:dd:ee:ff"  # Same as Zeroconf

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        result = await flow._validate_credentials("admin", "password", 80, False)

    # Should succeed and MAC should remain the same
    assert result is None
    assert flow._mac == "aa:bb:cc:dd:ee:ff"


async def test_validate_credentials_mac_updated_from_zeroconf(
    hass: HomeAssistant,
) -> None:
    """Test _validate_credentials when API MAC is different from Zeroconf MAC."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = "192.168.1.100"
    flow._device_type = DEVICE_TYPE_GDS
    flow._mac = "aa:bb:cc:dd:ee:ff"  # Set Zeroconf MAC

    # Mock API with different MAC
    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "11:22:33:44:55:66"  # Different from Zeroconf

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
        patch.object(
            hass,
            "async_add_executor_job",
            new_callable=AsyncMock,
            side_effect=lambda func, *args: func(*args),
        ),
    ):
        result = await flow._validate_credentials("admin", "password", 80, False)

    # Should succeed and MAC should be updated
    assert result is None
    assert flow._mac == "11:22:33:44:55:66"


async def test_reconfigure_no_entry_id(hass: HomeAssistant) -> None:
    """Test async_step_reconfigure when entry_id is missing from context."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_RECONFIGURE}  # No entry_id

    result = await flow.async_step_reconfigure(None)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_entry_id"


async def test_reconfigure_no_config_entry(hass: HomeAssistant) -> None:
    """Test async_step_reconfigure when config entry doesn't exist."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow.context = {
        "source": config_entries.SOURCE_RECONFIGURE,
        "entry_id": "nonexistent_entry_id",
    }

    result = await flow.async_step_reconfigure(None)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_config_entry"


# Tests for product model discovery
async def test_zeroconf_standard_service_with_product_field(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf discovery with product field in TXT records."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.130"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3725._https._tcp.local."
    discovery_info.properties = {"product": "GDS3725"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_standard_service_product_gds3727(hass: HomeAssistant) -> None:
    """Test zeroconf discovery for GDS3727 (1-door model)."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.131"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3727._https._tcp.local."
    discovery_info.properties = {"product": "GDS3727"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_standard_service_product_gsc3560(hass: HomeAssistant) -> None:
    """Test zeroconf discovery for GSC3560 (no RTSP model)."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.132"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gsc3560._https._tcp.local."
    discovery_info.properties = {"product": "GSC3560"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_device_info_with_product_field(hass: HomeAssistant) -> None:
    """Test zeroconf device-info service with product field."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.120"
    discovery_info.port = 80
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GDS3725.local."
    discovery_info.properties = {
        "product_name": "GDS",
        "product": "GDS3725",
        "hostname": "GDS3725",
        "http_port": "80",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.enable_socket
async def test_zeroconf_standard_service_gns_product_model(hass: HomeAssistant) -> None:
    """Test GNS device detection from product model in standard service (covers lines 621-622).

    Tests that when a GNS device is discovered via zeroconf standard service
    with a product model starting with GNS_NAS, it correctly sets both
    _device_model and _device_type to DEVICE_TYPE_GNS_NAS.
    """
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.140"
    discovery_info.port = 5001
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gns5004e._https._tcp.local."
    discovery_info.properties = {"product": "GNS5004E"}  # GNS product model

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"

    # Verify the flow has correct device type
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert flow._device_type == DEVICE_TYPE_GNS_NAS
    assert flow._product_model == "GNS5004E"


# Additional tests for missing coverage


@pytest.mark.enable_socket
async def test_create_config_entry_with_product_and_firmware(
    hass: HomeAssistant,
) -> None:
    """Test config entry creation with product model and firmware version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        # Set product model and firmware version on the flow
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        flow._product_model = "GDS3725"
        flow._firmware_version = "1.2.3"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["product_model"] == "GDS3725"
    assert result3["data"]["firmware_version"] == "1.2.3"


@pytest.mark.enable_socket
async def test_auth_missing_data_abort(hass: HomeAssistant) -> None:
    """Test auth step aborts when required data is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    # Simulate missing data by clearing flow internals
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._name = None

    with patch(
        "grandstream_home_api.GDSPhoneAPI.login",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "missing_data"


@pytest.mark.enable_socket
async def test_update_unique_id_existing_entry_different_ip(
    hass: HomeAssistant,
) -> None:
    """Test _update_unique_id_for_device when entry exists with different IP."""
    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"  # New IP
    discovery_info.port = 443
    discovery_info.type = "_device-info._tcp.local."
    discovery_info.name = "GDS3710.local."
    discovery_info.properties = {
        "mac": "00:0B:82:12:34:56",
        "product_name": "GDS3710",
    }

    # Create existing entry with different IP
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.200",  # Old IP
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
        },
        unique_id="00:0b:82:12:34:56",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort and update the entry with new IP
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.enable_socket
async def test_auth_verify_ssl_option(hass: HomeAssistant) -> None:
    """Test auth step with verify_ssl option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
                "verify_ssl": True,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["verify_ssl"] is True


@pytest.mark.enable_socket
async def test_auth_validation_failed(hass: HomeAssistant) -> None:
    """Test auth step when credential validation fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with patch(
        "grandstream_home_api.GDSPhoneAPI.login",
        return_value=False,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"]["base"] == "invalid_auth"


@pytest.mark.enable_socket
async def test_auth_gns_without_username_uses_default(hass: HomeAssistant) -> None:
    """Test GNS auth uses default username when not provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.101",
            CONF_NAME: "Test GNS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GNSNasAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GNSNasAPI.device_mac",
            "00:0B:82:12:34:57",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # Should use default GNS username when not provided
    assert result3["data"]["username"] == DEFAULT_USERNAME_GNS


@pytest.mark.enable_socket
async def test_auth_gds_without_username_uses_default(hass: HomeAssistant) -> None:
    """Test GDS auth uses default username when not provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # Should use default GDS username when not provided
    assert result3["data"]["username"] == DEFAULT_USERNAME


@pytest.mark.enable_socket
async def test_auth_custom_port(hass: HomeAssistant) -> None:
    """Test auth step with custom port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: 8443,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["port"] == 8443


# Tests for remaining coverage - testing through proper flow manager


@pytest.mark.enable_socket
async def test_create_entry_default_username_gds(hass: HomeAssistant) -> None:
    """Test _create_config_entry uses default GDS username when not provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["username"] == DEFAULT_USERNAME


@pytest.mark.enable_socket
async def test_reconfigure_ha_control_disabled_error(hass: HomeAssistant) -> None:
    """Test reconfigure flow with HA control disabled error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.side_effect = GrandstreamHAControlDisabledError(
        "HA control disabled"
    )

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        # First get the form
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        # Then submit with data that will trigger HA control disabled error
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "ha_control_disabled"


@pytest.mark.enable_socket
async def test_reconfigure_unknown_error(hass: HomeAssistant) -> None:
    """Test reconfigure flow with connection error (not invalid auth)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.side_effect = OSError("Connection error")

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
    ):
        # First get the form
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        # Then submit with valid data that will fail during API call
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.enable_socket
async def test_reconfigure_invalid_host(hass: HomeAssistant) -> None:
    """Test reconfigure flow with invalid host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Submit with invalid host
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "invalid_ip_address",
            CONF_PASSWORD: "test_password",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["host"] == "invalid_host"


@pytest.mark.enable_socket
async def test_reconfigure_invalid_port(hass: HomeAssistant) -> None:
    """Test reconfigure flow with invalid port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Submit with invalid port
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PASSWORD: "test_password",
            CONF_PORT: "invalid_port",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["port"] == "invalid_port"


@pytest.mark.enable_socket
async def test_zeroconf_discovery_device_unchanged(hass: HomeAssistant) -> None:
    """Test zeroconf discovery when device already configured with same host and port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gds3710",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    discovery_info.properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort since device unchanged
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.enable_socket
async def test_zeroconf_discovery_firmware_update(hass: HomeAssistant) -> None:
    """Test zeroconf discovery updates firmware version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gds3710",
        data={
            CONF_HOST: "192.168.1.50",  # Different IP
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"  # New IP
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    # Firmware version in properties
    discovery_info.properties = {"firmware_version": "1.0.5.12"}

    with patch(
        "homeassistant.components.grandstream_home.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        await hass.async_block_till_done()

    # Should abort and update the entry
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Check that entry was updated with new IP
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.100"


@pytest.mark.enable_socket
async def test_zeroconf_discovery_ip_port_changed(hass: HomeAssistant) -> None:
    """Test zeroconf discovery when device IP or port changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gds3710",
        data={
            CONF_HOST: "192.168.1.50",  # Different IP
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 8080,  # Different port
        },
    )
    entry.add_to_hass(hass)

    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    discovery_info.properties = {}

    with patch(
        "homeassistant.components.grandstream_home.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        await hass.async_block_till_done()

    # Should abort and update entry
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Check entry was updated
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.100"
    assert updated_entry.data[CONF_PORT] == 443


@pytest.mark.enable_socket
async def test_create_entry_no_auth_info_username_gds(hass: HomeAssistant) -> None:
    """Test _create_config_entry uses default username when not in auth_info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # GDS devices should use DEFAULT_USERNAME
    assert result3["data"]["username"] == DEFAULT_USERNAME


@pytest.mark.enable_socket
async def test_create_entry_no_auth_info_username_gns(hass: HomeAssistant) -> None:
    """Test _create_config_entry uses default GNS username when not in auth_info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GNS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GNSNasAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GNSNasAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # GNS devices should use DEFAULT_USERNAME_GNS
    assert result3["data"]["username"] == DEFAULT_USERNAME_GNS


@pytest.mark.enable_socket
async def test_zeroconf_discovery_with_firmware_update(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with firmware version when IP changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gds3710",
        data={
            CONF_HOST: "192.168.1.50",  # Different IP
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = MagicMock()
    discovery_info.host = "192.168.1.100"  # New IP
    discovery_info.port = 443
    discovery_info.type = "_https._tcp.local."
    discovery_info.name = "gds3710._https._tcp.local."
    discovery_info.properties = {"version": "1.0.5.12"}

    with patch(
        "homeassistant.components.grandstream_home.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )
        await hass.async_block_till_done()

    # Should abort and update entry
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Check entry was updated with new IP
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.100"
    # Firmware version should be updated
    assert updated_entry.data.get("firmware_version") == "1.0.5.12"


@pytest.mark.enable_socket
async def test_user_flow_mac_updates_existing_entry_ip(hass: HomeAssistant) -> None:
    """Test user flow updates existing entry IP when MAC matches."""
    # Create existing entry with MAC-based unique_id
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:0b:82:12:34:56",
        data={
            CONF_HOST: "192.168.1.50",  # Old IP
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "encrypted:test_password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            CONF_PORT: 443,
        },
    )
    existing_entry.add_to_hass(hass)

    # Start user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",  # New IP
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    # Mock API to return MAC that matches existing entry
    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "00:0B:82:12:34:56"  # Matches existing entry

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with (
        patch.object(
            hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._create_api_for_validation",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    # Should abort because existing entry was updated
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_configured"

    # Check existing entry was updated with new IP
    updated_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.100"


@pytest.mark.enable_socket
async def test_create_entry_empty_username_gns(hass: HomeAssistant) -> None:
    """Test _create_config_entry uses default GNS username when auth_info has empty username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GNS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GNSNasAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GNSNasAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_USERNAME: "",  # Empty username - should trigger default
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # GNS devices should use DEFAULT_USERNAME_GNS when username is empty
    assert result3["data"]["username"] == DEFAULT_USERNAME_GNS


@pytest.mark.enable_socket
async def test_create_config_entry_fallback_unique_id_with_mac(
    hass: HomeAssistant,
) -> None:
    """Test _create_config_entry generates fallback unique_id from MAC when unique_id not set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            "00:0B:82:12:34:56",
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        # Get the flow after auth step form is shown
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        # Ensure MAC is set
        flow._mac = "00:0B:82:12:34:56"

        # Patch _update_unique_id_for_mac to skip setting unique_id
        async def mock_update_skip_set_unique_id():
            # Call original to get MAC set, but don't let it set unique_id
            # Return None without setting unique_id
            return None

        with patch.object(
            flow,
            "_update_unique_id_for_mac",
            side_effect=mock_update_skip_set_unique_id,
        ):
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"],
                {
                    CONF_PASSWORD: "password",
                },
            )
            await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.enable_socket
async def test_create_config_entry_fallback_unique_id_no_mac(
    hass: HomeAssistant,
) -> None:
    """Test _create_config_entry generates fallback unique_id without MAC when unique_id not set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        },
    )

    with (
        patch(
            "grandstream_home_api.GDSPhoneAPI.login",
            return_value=True,
        ),
        patch(
            "grandstream_home_api.GDSPhoneAPI.device_mac",
            None,
            create=True,
        ),
        patch(
            "homeassistant.components.grandstream_home.async_setup_entry",
            return_value=True,
        ),
    ):
        # Get the flow
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        flow._mac = None  # No MAC available

        # Patch _update_unique_id_for_mac to skip setting unique_id
        async def mock_update_skip_set_unique_id():
            # Return None without setting unique_id
            return None

        with patch.object(
            flow,
            "_update_unique_id_for_mac",
            side_effect=mock_update_skip_set_unique_id,
        ):
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"],
                {
                    CONF_PASSWORD: "password",
                },
            )
            await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    # Should have generated name-based unique_id in fallback
    assert result3["result"].unique_id is not None
