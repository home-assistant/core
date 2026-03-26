"""Tests for the SNMP config flow."""

from unittest.mock import Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant import config_entries
from homeassistant.components.snmp.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.snmp.const import CONF_IMPORTED_BY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user setup flow (v1/v2c)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 1: Basic info
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "version": "1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"

    # Step 2: V1/V2c Auth
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "community": "public",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.1"
    assert result["data"] == {
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        "community": "public",
        "port": 161,
        "version": "1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_v3_success(hass: HomeAssistant) -> None:
    """Test successful user setup flow (v3)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1: Basic info
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "version": "3",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    # Step 2: V3 Auth
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "auth_user",
                "auth_key": "auth_password",
                "auth_protocol": "hmac-sha",
                "priv_key": "priv_password",
                "priv_protocol": "aes-cfb-128",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["version"] == "3"
    assert result["data"]["username"] == "auth_user"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "version": "1",
        },
    )

    # Step 2
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=("Timeout", None, None, None),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "community": "public",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful YAML import flow."""
    with patch(
        "homeassistant.components.snmp.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        CONF_IMPORTED_BY: "device_tracker",
    }
    assert len(mock_setup.mock_calls) == 1


async def test_import_flow_already_configured(hass: HomeAssistant) -> None:
    """Test YAML import flow aborts if already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.1_1.3.6.1.4.1.2021.10.1.3.1",
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts if already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.1_1.3.6.1.4.1.2021.10.1.3.1",
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "version": "1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_oid_short(hass: HomeAssistant) -> None:
    """Test user setup flow failure - OID too short (serialization error)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1: Basic info with OID "1"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1",
            "version": "1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"

    # Step 2: V1 Auth fails during validation of baseoid "1"
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            side_effect=[
                (None, None, None, [[OctetString("98F")]]),  # sysDescr.0 succeeds
                PySnmpError("Short OID 1"),  # baseoid "1" fails
            ],
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "community": "public",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert "Short OID 1" in result["description_placeholders"]["error"]


async def test_user_flow_v3_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "version": "3",
        },
    )

    # Step 2: V3 Auth fails (err_status returned by get_cmd)
    mock_err_status = Mock()
    mock_err_status.prettyPrint.return_value = "usmStatsWrongDigests"
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, mock_err_status, None, None),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert "usmStatsWrongDigests" in result["description_placeholders"]["error"]


async def test_user_flow_timeout_generic(hass: HomeAssistant) -> None:
    """Test user setup flow failure - timeout on sysDescr."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=("No response", None, None, None),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert "No response" in result["description_placeholders"]["error"]


async def test_user_flow_invalid_oid_exception(hass: HomeAssistant) -> None:
    """Test user setup flow failure - OID exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.ObjectIdentity",
        side_effect=PySnmpError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
                "version": "1",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"baseoid": "invalid_oid"}


async def test_user_flow_v1_v2c_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.validate_input",
        side_effect=InvalidAuth("Invalid community"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_v1_v2c_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.validate_input",
        side_effect=PySnmpError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_v3_auth_key_required_for_priv(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 auth key required for priv."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "user", "priv_key": "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_key_required_for_priv"}


async def test_user_flow_v3_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.validate_input",
        side_effect=PySnmpError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_validate_input_ipv6_fallback(hass: HomeAssistant) -> None:
    """Test validate_input with IPv6 fallback."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            return_value="mock_target",
        ) as mock_create6,
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "2c",
                "community": "public",
            },
        )
        mock_create6.assert_called()


async def test_validate_input_fail_all(hass: HomeAssistant) -> None:
    """Test validate_input failing both IPv4 and IPv6."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            side_effect=PySnmpError,
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "2c",
                "community": "public",
            },
        )


async def test_validate_input_unexpected_error(hass: HomeAssistant) -> None:
    """Test validate_input with an unexpected error during target creation."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "2c",
                "community": "public",
            },
        )


async def test_validate_input_v3_no_keys(hass: HomeAssistant) -> None:
    """Test validate_input with SNMP v3 and no auth/priv keys."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "3",
                "username": "test-user",
            },
        )


async def test_validate_input_pysnmp_error_auth(hass: HomeAssistant) -> None:
    """Test validate_input with PySnmpError during auth creation."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.util.UsmUserData",
            side_effect=PySnmpError,
        ),
        pytest.raises(InvalidAuth),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "3",
                "username": "test-user",
            },
        )


async def test_validate_input_wrong_value_error(hass: HomeAssistant) -> None:
    """Test validate_input with WrongValueError during get_cmd."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            side_effect=WrongValueError,
        ),
        pytest.raises(InvalidAuth),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "3",
                "username": "test-user",
            },
        )


async def test_validate_input_pysnmp_error_get(hass: HomeAssistant) -> None:
    """Test validate_input with PySnmpError during get_cmd."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            side_effect=PySnmpError,
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(
            hass,
            {
                "host": "1.2.3.4",
                "baseoid": "1.3.6.1.2.1.1",
                "version": "3",
                "username": "test-user",
            },
        )


async def test_user_flow_v3_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.validate_input",
        side_effect=CannotConnect("Cannot connect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
