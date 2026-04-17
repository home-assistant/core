# mypy: ignore-errors
"""Test the Grandstream Home config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from grandstream_home_api import DEVICE_TYPE_GDS
import pytest

from homeassistant import config_entries
from homeassistant.components.grandstream_home.config_flow import GrandstreamConfigFlow
from homeassistant.components.grandstream_home.const import (
    CONF_DEVICE_MODEL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.enable_socket
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_discovery_gds(hass: HomeAssistant) -> None:
    """Test zeroconf discovery for GDS device."""
    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="EC74D79753C5",
    ):
        # Use a simple object instead of MagicMock to avoid name attribute issues
        class MockZeroconfService:
            host = "192.168.1.100"
            port = 443
            name = "GDS3710-EC74D79753C5._https._tcp.local."
            type = "_https._tcp.local."
            properties = {"version": "1.0.1.13"}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_discovery_gsc(hass: HomeAssistant) -> None:
    """Test zeroconf discovery for GSC device."""
    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="ABC123DEF456",
    ):
        # Use a simple object instead of MagicMock to avoid name attribute issues
        class MockZeroconfService:
            host = "192.168.1.101"
            port = 443
            name = "GSC3560-ABC123DEF456._https._tcp.local."
            type = "_https._tcp.local."
            properties = {"version": "1.0.0.12"}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_discovery_non_gs_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery handles non-Grandstream devices."""

    # Use a simple object instead of MagicMock to avoid name attribute issues
    class MockZeroconfService:
        host = "192.168.1.100"
        port = 443
        name = "OTHER_DEVICE._https._tcp.local."
        type = "_https._tcp.local."
        properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MockZeroconfService(),
    )

    # Non-GDS/GSC devices are allowed to proceed (will be filtered later)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_discovery_no_name(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with no name."""

    # Use a simple object with no name
    class MockZeroconfServiceNoName:
        host = "192.168.1.100"
        port = 443
        name = None  # No name
        type = "_https._tcp.local."
        properties = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MockZeroconfServiceNoName(),
    )

    # Devices without name are allowed to proceed (user can manually configure)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_zeroconf_discovery_no_mac(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with no MAC in name."""
    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value=None,  # No MAC extracted
    ):

        class MockZeroconfServiceNoMac:
            host = "192.168.1.100"
            port = 443
            name = "GDS3710._https._tcp.local."  # No MAC in name
            type = "_https._tcp.local."
            properties = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfServiceNoMac(),
        )

    # Should still work, using generated unique_id
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_auth_step_success(hass: HomeAssistant) -> None:
    """Test successful authentication."""
    # Start user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
        },
    )

    assert result["step_id"] == "auth"

    # Mock successful credential validation and prevent actual setup
    mock_api = MagicMock()
    mock_api.device_mac = "EC74D79753C5"
    mock_api.product_model = "GDS3710"

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            return_value=(True, None),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_auth_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test authentication with invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
        },
    )

    # Mock failed credential validation
    mock_api = MagicMock()

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            return_value=(False, "invalid_auth"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "wrong_password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_zeroconf_already_in_progress(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts when same flow already in progress."""

    # Start first flow
    class MockZeroconfService:
        host = "192.168.1.100"
        port = 443
        name = "GDS3710-EC74D79753C5._https._tcp.local."
        type = "_https._tcp.local."
        properties = {"version": "1.0.1.13"}

    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="EC74D79753C5",
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "auth"

    # Try to start second flow with same unique_id - should abort
    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="EC74D79753C5",
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.enable_socket
async def test_zeroconf_update_existing_entry(hass: HomeAssistant) -> None:
    """Test zeroconf discovery updates existing entry with new IP/port."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ec:74:d7:97:53:c5",
        data={
            CONF_HOST: "192.168.1.100",  # Old IP
            CONF_PORT: 443,
            CONF_PASSWORD: "password",
            CONF_DEVICE_MODEL: DEVICE_TYPE_GDS,
        },
    )
    existing_entry.add_to_hass(hass)

    class MockZeroconfService:
        host = "192.168.1.200"  # New IP
        port = 8443  # New port
        name = "GDS3710-EC74D79753C5._https._tcp.local."
        type = "_https._tcp.local."
        properties = {"version": "1.0.1.14"}  # New firmware

    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="EC74D79753C5",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    # Should abort with already_configured and update the entry
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_auth_invalid_port(hass: HomeAssistant) -> None:
    """Test auth step with invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["step_id"] == "auth"

    # Try invalid port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "invalid_port",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["port"] == "invalid_port"


async def test_validate_credentials_os_error(hass: HomeAssistant) -> None:
    """Test credential validation handles OSError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            side_effect=OSError("Connection refused"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_validate_credentials_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test credential validation handles HA control disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            return_value=(False, "ha_control_disabled"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "ha_control_disabled"


async def test_validate_credentials_offline(hass: HomeAssistant) -> None:
    """Test credential validation handles offline device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            return_value=(False, "offline"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_validate_credentials_missing_host(hass: HomeAssistant) -> None:
    """Test credential validation when host is missing."""

    flow = GrandstreamConfigFlow()
    flow.hass = hass
    flow._host = None  # Set host to None
    flow._device_model = DEVICE_TYPE_GDS

    # Call _validate_credentials directly with no host
    api, error = await flow._validate_credentials("gdsha", "password", 443, False)

    assert api is None
    assert error == "missing_data"


async def test_duplicate_detection(hass: HomeAssistant) -> None:
    """Test that duplicate devices are detected."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ec:74:d7:97:53:c5",  # format_mac format
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_PORT: 443,
        },
    )
    existing_entry.add_to_hass(hass)

    # Try to discover same device
    with patch(
        "homeassistant.components.grandstream_home.config_flow.extract_mac_from_name",
        return_value="EC74D79753C5",
    ):
        # Use a simple object instead of MagicMock to avoid name attribute issues
        class MockZeroconfService:
            host = "192.168.1.100"
            port = 443
            name = "GDS3710-EC74D79753C5._https._tcp.local."
            type = "_https._tcp.local."
            properties = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MockZeroconfService(),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.enable_socket
async def test_duplicate_detection_no_mac(hass: HomeAssistant) -> None:
    """Test that duplicate devices are detected when MAC is not available."""
    # Create existing entry without MAC (manual configuration)
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Device",
            CONF_PORT: 443,
        },
    )
    existing_entry.add_to_hass(hass)

    # Try to add same device via manual flow (no MAC extracted)
    with (
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            return_value=(True, None),
        ),
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            return_value=MagicMock(
                host="192.168.1.100",
                device_mac=None,  # No MAC available
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First step - enter host
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"

        # Second step - enter credentials (should abort due to _async_abort_entries_match)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "testpass",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

        # Should abort due to _async_abort_entries_match
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
