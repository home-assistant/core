"""Tests for the SNMP config flow."""

from unittest.mock import MagicMock, Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant import config_entries
from homeassistant.components.snmp.config_flow import (
    AUTH_PROTOCOL_SELECTOR,
    PRIV_PROTOCOL_SELECTOR,
    SNMP_VERSION_SELECTOR,
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.snmp.const import (
    DOMAIN,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.config_entries import SubentryFlowContext
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector

from . import mock_entry

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
    """Test that YAML is imported as a device with a device tracker subentry."""
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
    entry = result["result"]
    assert entry.data == {
        "host": "192.168.1.1",
        "port": 161,
        "version": "1",
        "community": "public",
    }

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
    assert len(subentries) == 1
    assert subentries[0].data["baseoid"] == "1.3.6.1.4.1.2021.10.1.3.1"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_with_v3_credentials_aborts(hass: HomeAssistant) -> None:
    """Test YAML import aborts when the configuration uses SNMPv3 credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.1",
            "auth_key": "auth_key",
            "priv_key": "priv_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "credentials_required"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test YAML import flow aborts if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.1",
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
            "version": "1",
        },
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
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
            {
                "username": "user",
                "auth_key": "correct_pass",
                "auth_protocol": "hmac-sha",
            },
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
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
            "usm_wrong_digests",
            {
                "username": "user",
                "auth_key": "correct_pass",
                "auth_protocol": "hmac-sha",
            },
            id="wrong_digest",
        ),
        pytest.param(
            "3",
            errind.unknownUserName,
            {"username": "nouser", "auth_key": "pass", "auth_protocol": "hmac-sha"},
            "invalid_auth",
            {"username": "validuser", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
        {"host": "1.1.1.1", "version": version},
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


async def _async_start_subentry_flow(hass: HomeAssistant, entry: MockConfigEntry):
    """Start the device tracker subentry flow of an entry."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE_TRACKER),
        context=SubentryFlowContext(source=config_entries.SOURCE_USER),
    )


async def test_subentry_flow_user(hass: HomeAssistant) -> None:
    """Test adding a device tracker to an SNMP device."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"baseoid": "1.3.6.1.2.1.4.22.1.2", "interval_seconds": 60},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
    assert len(subentries) == 1
    assert subentries[0].data == {
        "baseoid": "1.3.6.1.2.1.4.22.1.2",
        "interval_seconds": 60,
    }


async def test_subentry_flow_invalid_oid(hass: HomeAssistant) -> None:
    """Test that the subentry flow rejects an OID pysnmp cannot resolve."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"baseoid": "not_an_oid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"baseoid": "invalid_oid"}

    # Retry with a valid OID
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"baseoid": "1.3.6.1.2.1.4.22.1.2"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)


async def test_subentry_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that a device can only have one device tracker."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test changing the table of an existing device tracker."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"baseoid": "1.3.6.1.2.1.17.4.3.1.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data["baseoid"] == "1.3.6.1.2.1.17.4.3.1.1"


async def test_user_flow_v1_v2c_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user setup flow failure - v1/v2c invalid auth, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "version": "1"},
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
        {"host": "1.1.1.1", "version": "1"},
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
        {"host": "1.1.1.1", "version": "3"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "user", "priv_key": "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"auth_key": "auth_key_required_for_priv"}

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
        {"host": "1.1.1.1", "version": "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=PySnmpError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
            result["flow_id"],
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
        {"host": "1.2.3.4", "version": "3"},
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
        {"host": "1.2.3.4", "version": "3"},
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
        {"host": "1.2.3.4", "version": "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=WrongValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
        {"host": "1.1.1.1", "version": "1"},
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
        {"host": "1.1.1.1", "version": "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.validate_input",
        side_effect=CannotConnect("Cannot connect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
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
            result["flow_id"],
            {"username": "user", "auth_key": "pass", "auth_protocol": "hmac-sha"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_with_port_and_interval(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test import flow with a custom port and poll interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.1",
            "port": 1161,
            "community": "public",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            "interval_seconds": 60,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id is None
    assert entry.data["host"] == "192.168.1.1"
    assert entry.data["port"] == 1161

    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)[0]
    assert subentry.data["baseoid"] == "1.3.6.1.4.1.2021.10.1.3.1"
    assert subentry.data["interval_seconds"] == 60


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("context_input", "expected_type"),
    [
        pytest.param({}, FlowResultType.CREATE_ENTRY, id="no_context"),
        pytest.param(
            {"context_name": "other"}, FlowResultType.CREATE_ENTRY, id="other_context"
        ),
        pytest.param(
            {"context_name": "test-context"}, FlowResultType.ABORT, id="same_context"
        ),
    ],
)
async def test_user_flow_context_is_part_of_the_device(
    hass: HomeAssistant,
    context_input: dict[str, str],
    expected_type: FlowResultType,
) -> None:
    """Test that only an identical SNMPv3 context is a duplicate device."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.1.1",
        data={
            "host": "192.168.1.1",
            "port": 161,
            "version": "3",
            "username": "user",
            "context_name": "test-context",
        },
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", "version": "3"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", **context_input}
        )
        await hass.async_block_till_done()

    assert result["type"] is expected_type


@pytest.mark.parametrize(
    ("user_input", "expected_errors"),
    [
        pytest.param(
            {"username": "user", "auth_key": "auth-key", "auth_protocol": "none"},
            {"auth_protocol": "auth_protocol_required_for_auth_key"},
            id="auth_key_without_protocol",
        ),
        pytest.param(
            {"username": "user", "auth_protocol": "hmac-sha"},
            {"auth_key": "auth_key_required_for_auth_protocol"},
            id="auth_protocol_without_key",
        ),
        pytest.param(
            {
                "username": "user",
                "priv_key": "priv-key",
                "priv_protocol": "aes-cfb-128",
            },
            {"auth_key": "auth_key_required_for_priv"},
            id="priv_without_auth",
        ),
        pytest.param(
            {
                "username": "user",
                "auth_key": "auth-key",
                "auth_protocol": "hmac-sha",
                "priv_key": "priv-key",
                "priv_protocol": "none",
            },
            {"priv_protocol": "priv_protocol_required_for_priv_key"},
            id="priv_key_without_protocol",
        ),
        pytest.param(
            {
                "username": "user",
                "auth_key": "auth-key",
                "auth_protocol": "hmac-sha",
                "priv_protocol": "aes-cfb-128",
            },
            {"priv_key": "priv_key_required_for_priv_protocol"},
            id="priv_protocol_without_key",
        ),
    ],
)
async def test_user_flow_v3_incoherent_credentials(
    hass: HomeAssistant,
    user_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Test that keys and protocols which do not pair up are rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", "version": "3"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"
    assert result["errors"] == expected_errors


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_auth_without_privacy(hass: HomeAssistant) -> None:
    """Test that authentication without privacy is accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", "version": "3"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "auth-key", "auth_protocol": "hmac-sha"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["auth_protocol"] == "hmac-sha"
    assert "priv_key" not in result["data"]


@pytest.mark.parametrize(
    ("selector", "translation_key", "options"),
    [
        pytest.param(
            AUTH_PROTOCOL_SELECTOR,
            "auth_protocol",
            list(MAP_AUTH_PROTOCOLS),
            id="auth_protocol",
        ),
        pytest.param(
            PRIV_PROTOCOL_SELECTOR,
            "priv_protocol",
            list(MAP_PRIV_PROTOCOLS),
            id="priv_protocol",
        ),
        pytest.param(
            SNMP_VERSION_SELECTOR,
            "version",
            list(SNMP_VERSIONS),
            id="version",
        ),
    ],
)
def test_selectors_offer_translated_values(
    selector: SelectSelector,
    translation_key: str,
    options: list[str],
) -> None:
    """Test that every supported value is offered through a translated dropdown."""
    select = selector.serialize()["selector"]["select"]

    assert select["options"] == options
    assert select["translation_key"] == translation_key


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_updates_credentials(hass: HomeAssistant) -> None:
    """Test that the community string of an entry can be changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.1.1",
        data={
            "host": "192.168.1.1",
            CONF_PORT: 1161,
            "version": "1",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", CONF_PORT: 1161, "version": "1"}
    )
    assert result["step_id"] == "v1_v2c"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "private"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["community"] == "private"
    assert entry.data[CONF_PORT] == 1161


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_keeps_entry_on_invalid_credentials(
    hass: HomeAssistant,
) -> None:
    """Test that credentials which do not work are reported and not stored."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", "version": "1"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(errind.unknownCommunityName, None, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"community": "wrong"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["community"] == "public"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_aborts_on_duplicate_device(
    hass: HomeAssistant,
) -> None:
    """Test that an entry cannot be reconfigured onto another device."""
    entry = mock_entry(host="192.168.1.1")
    entry.add_to_hass(hass)
    other_entry = mock_entry(host="192.168.1.2")
    other_entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.2", "version": "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "192.168.1.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_updates_credentials(hass: HomeAssistant) -> None:
    """Test that a v3 entry can be reauthenticated with new keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.1.1",
        data={
            "host": "192.168.1.1",
            CONF_PORT: 161,
            "version": "3",
            "username": "user",
            "auth_key": "old-key",
            "auth_protocol": "hmac-sha",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "auth_key": "new-key", "auth_protocol": "hmac-sha"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["auth_key"] == "new-key"
    assert entry.data["host"] == "192.168.1.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_is_checked_after_credentials(hass: HomeAssistant) -> None:
    """Test that a v3 flow is not aborted before its context name is known."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.1", "version": "3"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "context_name": "other-context"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["context_name"] == "other-context"
