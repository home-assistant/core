"""Tests for the SNMP config flow."""

from unittest.mock import MagicMock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant import config_entries
from homeassistant.components.snmp.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.snmp.const import DOMAIN
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
    """Test user setup flow failure - cannot connect, then recovery."""
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

    # Step 2: fails
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

    # Step 2: retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"community": "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    }
    assert len(mock_setup.mock_calls) == 1


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test YAML import flow aborts if already configured."""
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


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts if already configured."""
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"community": "public"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_oid_short(hass: HomeAssistant) -> None:
    """Test user setup flow failure - OID too short, then recovery."""
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
    assert result["errors"] == {"base": "invalid_oid"}

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"community": "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 invalid auth, then recovery."""
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
    mock_err_status = MagicMock()
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
    assert result["errors"] == {"base": "usm_wrong_digests"}

    # Retry with correct credentials succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "correct_pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_generic_err_status(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 generic err_status, then recovery."""
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

    # Step 2: V3 Auth fails with a generic err_status (not wrongdigests/decryptionerror)
    mock_err_status = MagicMock()
    mock_err_status.prettyPrint.return_value = "authorizationError"
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

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "correct_pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_timeout_generic(hass: HomeAssistant) -> None:
    """Test user setup flow failure - timeout on sysDescr, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(errind.requestTimedOut, None, None, None),
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
    assert result["errors"] == {"base": "snmp_timeout"}

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_err_indication_wrong_digest(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 wrong digest indication, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(errind.wrongDigest, None, None, None),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "usm_wrong_digests"}

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "correct_pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_err_indication_unknown_user(hass: HomeAssistant) -> None:
    """Test user setup flow failure - unknown USM user, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(errind.unknownUserName, None, None, None),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "nouser", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "validuser", "auth_key": "pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_oid_exception(hass: HomeAssistant) -> None:
    """Test user setup flow failure - OID exception, then recovery."""
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

    # Retry with valid OID succeeds (goes to v1_v2c step)
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"community": "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v1_v2c_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c invalid auth, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
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

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "correct_community"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v1_v2c_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            side_effect=PySnmpError("Unknown error"),
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

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_auth_key_required_for_priv(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 auth key required for priv, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "user", "priv_key": "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_key_required_for_priv"}

    # Retry with auth_key provided succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "user",
                "auth_key": "authpass",
                "auth_protocol": "hmac-sha",
                "priv_key": "privpass",
                "priv_protocol": "aes-cfb-128",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            side_effect=PySnmpError("Unknown error"),
        ),
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
            side_effect=RuntimeError("Something unexpected"),
        ),
        pytest.raises(RuntimeError, match="Something unexpected"),
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
    """Test user setup flow failure - v3 cannot connect, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
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

    # Retry succeeds
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
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_with_port_and_context_name(hass: HomeAssistant) -> None:
    """Test import flow unique_id includes port and context_name."""
    with patch("homeassistant.components.snmp.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "192.168.1.1",
                "port": 1161,
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
                "community": "public",
                "context_name": "vlan100",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == "192.168.1.1_1161_1.3.6.1.4.1.2021.10.1.3.1_vlan100"
