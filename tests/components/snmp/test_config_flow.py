"""Tests for the SNMP config flow."""

from unittest.mock import MagicMock, Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant import config_entries
from homeassistant.components.snmp.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant, mock_setup_entry: Mock) -> None:
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
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
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


async def test_user_flow_v3_success(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
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


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=("Timeout", None, None, None),
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"community": "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_success(hass: HomeAssistant, mock_setup_entry: Mock) -> None:
    """Test successful YAML import flow."""
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
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_user_flow_v3_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, mock_err_status, None, None),
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "correct_pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_vacm_denied_sysdescr(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test v3 flow succeeds when sysDescr is denied by VACM but base OID works."""
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

    # Step 2: sysDescr.0 returns err_status (VACM denial) but base OID succeeds
    mock_err_status = MagicMock()
    mock_err_status.prettyPrint.return_value = "authorizationError"
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, mock_err_status, None, None),  # sysDescr.0 denied
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("version", "errindication", "step2_data", "expected_error", "retry_data"),
    [
        pytest.param(
            "1",
            errind.requestTimedOut,
            {"community": "public"},
            "snmp_timeout",
            {"community": "public"},
            id="timeout",
        ),
        pytest.param(
            "3",
            errind.wrongDigest,
            {"username": "user", "auth_key": "pass"},
            "usm_wrong_digests",
            {"username": "user", "auth_key": "correct_pass"},
            id="wrong_digest",
        ),
        pytest.param(
            "3",
            errind.unknownUserName,
            {"username": "nouser", "auth_key": "pass"},
            "invalid_auth",
            {"username": "validuser", "auth_key": "pass"},
            id="unknown_user",
        ),
    ],
)
async def test_user_flow_err_indication(
    hass: HomeAssistant,
    mock_setup_entry: Mock,
    version: str,
    errindication: object,
    step2_data: dict[str, str],
    expected_error: str,
    retry_data: dict[str, str],
) -> None:
    """Test user setup flow failure - various errindications, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": version},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(errindication, None, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], step2_data
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Retry succeeds
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], retry_data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_oid_exception(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"community": "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v1_v2c_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "correct_community"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v1_v2c_unknown_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user setup flow failure - v1/v2c unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=PySnmpError("Unknown error"),
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_auth_key_required_for_priv(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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


async def test_user_flow_v3_unknown_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user setup flow failure - v3 unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=PySnmpError("Unknown error"),
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_no_keys_success(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test successful v3 setup with only a username (no auth/priv keys)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.2.3.4", "baseoid": "1.3.6.1.2.1.1", "version": "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "test-user"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_auth_creation_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test v3 flow when UsmUserData creation fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.2.3.4", "baseoid": "1.3.6.1.2.1.1", "version": "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.util.UsmUserData",
        side_effect=PySnmpError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "test-user"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_v3_wrong_value_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test v3 flow when get_cmd raises WrongValueError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.2.3.4", "baseoid": "1.3.6.1.2.1.1", "version": "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=WrongValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "test-user", "auth_key": "pass"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "usm_wrong_digests"}


async def test_user_flow_transport_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user setup flow failure - transport creation fails (IPv4+IPv6), then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "baseoid": "1.3.6.1.2.1", "version": "1"},
    )

    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            side_effect=PySnmpError,
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_v3_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "auth_key": "pass"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_with_port_and_context_name(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test import flow with port and context_name."""
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
    assert entry.unique_id is None
    assert entry.data["host"] == "192.168.1.1"
    assert entry.data["port"] == 1161
    assert entry.data["baseoid"] == "1.3.6.1.4.1.2021.10.1.3.1"
    assert entry.data["context_name"] == "vlan100"
