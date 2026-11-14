"""Tests for the SNMP config flow."""

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.config_flow import (
    AUTH_PROTOCOL_SELECTOR,
    PRIV_PROTOCOL_SELECTOR,
    SNMP_VERSION_SELECTOR,
)
from homeassistant.components.snmp.const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VERSION,
    DOMAIN,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import SelectSelector

from . import ARP_TABLE_MAC_OID, mock_entry

MAC = "00:11:22:33:44:55"

# 1.3.6.1.2.1.17.4.3.1.1, the MAC column of the bridge forwarding table
BRIDGE_MAC_OID = "1.3.6.1.2.1.17.4.3.1.1"


@pytest.fixture
def mock_walk_empty() -> Iterator[None]:
    """Make any base OID readable by returning a walk without rows."""

    async def _walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        return
        yield  # pylint: disable=unreachable

    with patch("homeassistant.components.snmp.client.bulk_walk_cmd", side_effect=_walk):
        yield


@pytest.mark.usefixtures("mock_walk_empty")
async def test_user_flow_success(hass: HomeAssistant, mock_setup_entry: Mock) -> None:
    """Test successful user setup flow (v1/v2c)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_COMMUNITY: "public",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.1"
    assert result["data"] == {
        CONF_HOST: "192.168.1.1",
        CONF_COMMUNITY: "public",
        CONF_PORT: 161,
        CONF_VERSION: "1",
        CONF_CONTEXT_NAME: "",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # The device tracker subentry flow is chained right after the entry is created
    next_flow_type, next_flow_id = result["next_flow"]
    assert next_flow_type is FlowType.CONFIG_SUBENTRIES_FLOW

    result = await hass.config_entries.subentries.async_configure(
        next_flow_id, {CONF_BASEOID: ARP_TABLE_MAC_OID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert [subentry.subentry_type for subentry in entry.subentries.values()] == [
        SUBENTRY_TYPE_DEVICE_TRACKER
    ]


async def test_user_flow_v3_success(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test successful user setup flow (v3)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "3",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "auth_user",
                CONF_AUTH_KEY: "auth_password",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_PRIV_KEY: "priv_password",
                CONF_PRIV_PROTOCOL: "aes-cfb-128",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VERSION] == "3"
    assert result["data"][CONF_USERNAME] == "auth_user"
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["next_flow"][0] is FlowType.CONFIG_SUBENTRIES_FLOW


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - cannot connect, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "1",
        },
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=("Timeout", None, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_COMMUNITY: "public",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COMMUNITY: "public"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_config_entry")
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 invalid auth, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "3",
        },
    )

    mock_err_status = MagicMock()
    mock_err_status.prettyPrint.return_value = "usmStatsWrongDigests"
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, mock_err_status, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "usm_wrong_digests"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "correct_pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_vacm_denied_sysdescr(hass: HomeAssistant) -> None:
    """Test v3 flow succeeds when sysDescr is denied by VACM but base OID works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_VERSION: "3",
        },
    )

    mock_err_status = MagicMock()
    mock_err_status.prettyPrint.return_value = "authorizationError"
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, mock_err_status, None, None),  # sysDescr.0 denied
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("version", "errindication", "step2_data", "expected_error", "retry_data"),
    [
        pytest.param(
            "1",
            errind.requestTimedOut,
            {CONF_COMMUNITY: "public"},
            "snmp_timeout",
            {CONF_COMMUNITY: "public"},
            id="timeout",
        ),
        pytest.param(
            "1",
            errind.emptyResponse,
            {CONF_COMMUNITY: "public"},
            "snmp_timeout",
            {CONF_COMMUNITY: "public"},
            id="empty_response",
        ),
        pytest.param(
            "3",
            errind.decryptionError,
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            "usm_wrong_digests",
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "correct_pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            id="decryption_error",
        ),
        pytest.param(
            "3",
            errind.wrongDigest,
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            "usm_wrong_digests",
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "correct_pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            id="wrong_digest",
        ),
        pytest.param(
            "3",
            errind.unknownUserName,
            {
                CONF_USERNAME: "nouser",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            "invalid_auth",
            {
                CONF_USERNAME: "validuser",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            id="unknown_user",
        ),
        pytest.param(
            "3",
            # pysnmp reports an unknown context as the report PDU's OID
            errind.ReportPduReceived("1.3.6.1.6.3.12.1.5.0"),
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_CONTEXT_NAME: "missing",
            },
            "invalid_context",
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_CONTEXT_NAME: "existing",
            },
            id="unknown_context",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_err_indication(
    hass: HomeAssistant,
    version: str,
    errindication: object,
    step2_data: dict[str, str],
    expected_error: str,
    retry_data: dict[str, str],
) -> None:
    """Test user setup flow failure - various errindications, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: version},
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

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], retry_data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def _async_start_subentry_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> SubentryFlowResult:
    """Start the device tracker subentry flow of an entry."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE_TRACKER),
        context=SubentryFlowContext(source=SOURCE_USER),
    )


@pytest.mark.usefixtures("mock_walk_empty")
async def test_subentry_flow_user(hass: HomeAssistant) -> None:
    """Test adding a device tracker to an SNMP device."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
    assert len(subentries) == 1
    assert subentries[0].data == {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"}
    assert subentries[0].title == "1.3.6.1.2.1.4.22.1.2"
    assert subentries[0].unique_id == "1.3.6.1.2.1.4.22.1.2"


async def test_subentry_flow_single_tracker(hass: HomeAssistant) -> None:
    """Test that a device tracks a single table."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_walk_empty")
async def test_subentry_flow_invalid_oid(hass: HomeAssistant) -> None:
    """Test that the subentry flow rejects an OID pysnmp cannot resolve."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    result = await _async_start_subentry_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: "not_an_oid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASEOID: "invalid_oid"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)


@pytest.mark.usefixtures("mock_walk_empty")
@pytest.mark.parametrize(
    ("errindication", "expected_errors"),
    [
        pytest.param(errind.wrongDigest, {"base": "invalid_auth"}, id="auth_error"),
        pytest.param(
            errind.ReportPduReceived("1.3.6.1.6.3.12.1.5.0"),
            {"base": "invalid_context"},
            id="unknown_context",
        ),
        pytest.param(
            PySnmpError("walk failed"), {"base": "cannot_connect"}, id="walk_error"
        ),
    ],
)
async def test_subentry_flow_walk_failure(
    hass: HomeAssistant,
    errindication: errind.ErrorIndication | PySnmpError,
    expected_errors: dict[str, str],
) -> None:
    """Test that a device level failure is not reported on the Base OID field."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield errindication, None, None, []

    result = await _async_start_subentry_flow(hass, entry)
    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_walk_empty")
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
        {CONF_BASEOID: BRIDGE_MAC_OID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert subentry.data[CONF_BASEOID] == BRIDGE_MAC_OID
    assert subentry.title == BRIDGE_MAC_OID
    assert subentry.unique_id == BRIDGE_MAC_OID


@pytest.mark.usefixtures("mock_walk_empty")
async def test_subentry_flow_reconfigure_normalizes_oid(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the same table written differently keeps its trackers."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    entity_id = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        f"{subentry_id}_{MAC}",
        config_entry=entry,
        config_subentry_id=subentry_id,
    ).entity_id

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: f" {ARP_TABLE_MAC_OID}."},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_BASEOID] == ARP_TABLE_MAC_OID
    assert entity_registry.async_get(entity_id) is not None


@pytest.mark.usefixtures("mock_walk_empty")
async def test_subentry_flow_reconfigure_confirms_removing_trackers(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a table change removes the dropped trackers only once confirmed."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    entity_id = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        f"{subentry_id}_{MAC}",
        config_entry=entry,
        config_subentry_id=subentry_id,
    ).entity_id

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BASEOID: BRIDGE_MAC_OID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"count": "1"}
    assert entity_registry.async_get(entity_id) is not None

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_BASEOID] == BRIDGE_MAC_OID
    assert entity_registry.async_get(entity_id) is None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v1_v2c_invalid_auth(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c invalid auth, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(errind.unknownCommunityName, None, None, []),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "correct_community"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v1_v2c_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v1/v2c unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=PySnmpError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unexpected_error(hass: HomeAssistant) -> None:
    """Test that an unexpected exception is reported as an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "1"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_auth_key_required_for_priv(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 auth key required for priv, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "3"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PRIV_KEY: "pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_AUTH_KEY: "auth_key_required_for_priv"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "authpass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_PRIV_KEY: "privpass",
                CONF_PRIV_PROTOCOL: "aes-cfb-128",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_unknown_error(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 unknown error, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "3"},
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=PySnmpError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_no_keys_success(hass: HomeAssistant) -> None:
    """Test successful v3 setup with only a username (no auth/priv keys)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_VERSION: "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "test-user"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_auth_creation_error(hass: HomeAssistant) -> None:
    """Test v3 flow when UsmUserData creation fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_VERSION: "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.util.UsmUserData",
        side_effect=PySnmpError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "test-user"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Once the auth data can be created the flow finishes
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "test-user"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_wrong_value_error(hass: HomeAssistant) -> None:
    """Test v3 flow when get_cmd raises WrongValueError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_VERSION: "3"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        side_effect=WrongValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "usm_wrong_digests"}

    # Once the agent accepts the digests the flow finishes
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_transport_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - transport creation fails (IPv4+IPv6), then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "1"},
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
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "public"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - v3 cannot connect, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_VERSION: "3"},
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
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "pass",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("context_input", "expected_type"),
    [
        pytest.param({}, FlowResultType.CREATE_ENTRY, id="no_context"),
        pytest.param(
            {CONF_CONTEXT_NAME: "other"},
            FlowResultType.CREATE_ENTRY,
            id="other_context",
        ),
        pytest.param(
            {CONF_CONTEXT_NAME: "test-context"}, FlowResultType.ABORT, id="same_context"
        ),
    ],
)
async def test_user_flow_context_is_part_of_the_device(
    hass: HomeAssistant,
    context_input: dict[str, str],
    expected_type: FlowResultType,
) -> None:
    """Test that only an identical SNMPv3 context is a duplicate device."""
    existing = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="3",
        username="user",
        context_name="test-context",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "3"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "user", **context_input}
        )
        await hass.async_block_till_done()

    assert result["type"] is expected_type


@pytest.mark.parametrize(
    ("user_input", "expected_errors"),
    [
        pytest.param(
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "none",
            },
            {CONF_AUTH_PROTOCOL: "auth_protocol_required_for_auth_key"},
            id="auth_key_without_protocol",
        ),
        pytest.param(
            {CONF_USERNAME: "user", CONF_AUTH_PROTOCOL: "hmac-sha"},
            {CONF_AUTH_KEY: "auth_key_required_for_auth_protocol"},
            id="auth_protocol_without_key",
        ),
        pytest.param(
            {
                CONF_USERNAME: "user",
                CONF_PRIV_KEY: "priv-key",
                CONF_PRIV_PROTOCOL: "aes-cfb-128",
            },
            {CONF_AUTH_KEY: "auth_key_required_for_priv"},
            id="priv_without_auth",
        ),
        pytest.param(
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_PRIV_KEY: "priv-key",
                CONF_PRIV_PROTOCOL: "none",
            },
            {CONF_PRIV_PROTOCOL: "priv_protocol_required_for_priv_key"},
            id="priv_key_without_protocol",
        ),
        pytest.param(
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_PRIV_PROTOCOL: "aes-cfb-128",
            },
            {CONF_PRIV_KEY: "priv_key_required_for_priv_protocol"},
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
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "3"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"
    assert result["errors"] == expected_errors

    # A coherent set of credentials finishes the flow
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_auth_without_privacy(hass: HomeAssistant) -> None:
    """Test that authentication without privacy is accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "3"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AUTH_PROTOCOL] == "hmac-sha"
    assert CONF_PRIV_KEY not in result["data"]


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


async def test_reconfigure_flow_updates_credentials(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test that the community string of an entry can be changed."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=1161,
        version="1",
        community="public",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1", CONF_PORT: 1161, CONF_VERSION: "1"},
    )
    assert result["step_id"] == "v1_v2c"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "private"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_COMMUNITY] == "private"
    assert entry.data[CONF_PORT] == 1161
    # The entry had no update listener, so it has to be reloaded explicitly
    assert mock_setup_entry.called


async def test_reconfigure_flow_uses_update_listener(hass: HomeAssistant) -> None:
    """Test that a loaded entry is reloaded through its update listener."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    listener = AsyncMock()
    entry.add_update_listener(listener)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "1"}
    )
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "private"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_COMMUNITY] == "private"
    # The update listener is responsible for reloading the entry
    assert listener.called


async def test_reconfigure_flow_keeps_entry_on_invalid_credentials(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test that credentials which do not work are reported and not stored."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "1"}
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(errind.unknownCommunityName, None, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "wrong"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_COMMUNITY] == "public"

    # Working credentials finish the reconfigure and update the entry
    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "private"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_COMMUNITY] == "private"
    assert mock_setup_entry.called


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
        result["flow_id"], {CONF_HOST: "192.168.1.2", CONF_VERSION: "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_suggests_credentials(hass: HomeAssistant) -> None:
    """Test that reconfiguring prefills everything but the keys."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="3",
        username="user",
        auth_key="auth_password",
        auth_protocol="hmac-sha",
        priv_key="priv_password",
        priv_protocol="aes-cfb-128",
        context_name="other-context",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_PORT: 161, CONF_VERSION: "3"}
    )
    assert result["step_id"] == "v3"

    data_schema = result["data_schema"].schema
    assert get_schema_suggested_value(data_schema, CONF_USERNAME) == "user"
    assert get_schema_suggested_value(data_schema, CONF_AUTH_PROTOCOL) == "hmac-sha"
    assert get_schema_suggested_value(data_schema, CONF_PRIV_PROTOCOL) == "aes-cfb-128"
    assert get_schema_suggested_value(data_schema, CONF_CONTEXT_NAME) == "other-context"
    assert get_schema_suggested_value(data_schema, CONF_AUTH_KEY) is None
    assert get_schema_suggested_value(data_schema, CONF_PRIV_KEY) is None


async def test_reauth_flow_updates_credentials(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test that a v3 entry can be reauthenticated with new keys."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="3",
        username="user",
        auth_key="old-key",
        auth_protocol="hmac-sha",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"name": entry.title}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"
    data_schema = result["data_schema"].schema
    assert get_schema_suggested_value(data_schema, CONF_USERNAME) == "user"
    assert get_schema_suggested_value(data_schema, CONF_AUTH_KEY) is None

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "new-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_AUTH_KEY] == "new-key"
    assert entry.data[CONF_HOST] == "192.168.1.1"
    assert mock_setup_entry.called


async def test_reauth_flow_v1_v2c_does_not_suggest_community(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test that reauthenticating v1/v2c does not prefill the stored community."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="1",
        community="old-community",
        context_name="",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v1_v2c"
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_COMMUNITY) is None
    )

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_COMMUNITY: "new-community"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_COMMUNITY] == "new-community"
    assert mock_setup_entry.called


async def test_reauth_flow_drops_removed_privacy_key(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test that downgrading to authentication without privacy drops the key."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="3",
        username="user",
        auth_key="auth-key",
        auth_protocol="hmac-sha",
        priv_key="priv-key",
        priv_protocol="aes-cfb-128",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
                CONF_PRIV_PROTOCOL: "none",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PRIV_PROTOCOL] == "none"
    assert CONF_PRIV_KEY not in entry.data
    assert mock_setup_entry.called


async def test_reauth_flow_reloads_when_credentials_are_unchanged(
    hass: HomeAssistant,
) -> None:
    """Test that a reauth which changes nothing still reloads the entry."""
    entry = mock_entry(
        baseoid=None,
        host="192.168.1.1",
        port=161,
        version="3",
        username="user",
        auth_key="auth-key",
        auth_protocol="hmac-sha",
        priv_protocol="none",
        context_name="",
    )
    entry.add_to_hass(hass)
    listener = AsyncMock()
    entry.add_update_listener(listener)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as mock_schedule_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "auth-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # The update listener does not fire for an unchanged entry
    assert not listener.called
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.parametrize(
    (
        "entry_data",
        "errindication",
        "step_id",
        "rejected",
        "expected_error",
        "accepted",
        "expected_changes",
    ),
    [
        pytest.param(
            {CONF_VERSION: "1", CONF_COMMUNITY: "old-community"},
            errind.unknownCommunityName,
            "v1_v2c",
            {CONF_COMMUNITY: "wrong-community"},
            "invalid_auth",
            {CONF_COMMUNITY: "new-community"},
            {CONF_COMMUNITY: "new-community"},
            id="v1_v2c",
        ),
        pytest.param(
            {
                CONF_VERSION: "3",
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "old-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            errind.wrongDigest,
            "v3",
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "wrong-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            "usm_wrong_digests",
            {
                CONF_USERNAME: "user",
                CONF_AUTH_KEY: "new-key",
                CONF_AUTH_PROTOCOL: "hmac-sha",
            },
            {CONF_AUTH_KEY: "new-key"},
            id="v3",
        ),
    ],
)
async def test_reauth_flow_retries_rejected_credentials(
    hass: HomeAssistant,
    mock_setup_entry: Mock,
    entry_data: dict[str, Any],
    errindication: object,
    step_id: str,
    rejected: dict[str, str],
    expected_error: str,
    accepted: dict[str, str],
    expected_changes: dict[str, str],
) -> None:
    """Test that rejected credentials are reported and can be retried."""
    entry = mock_entry(baseoid=None, **entry_data)
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == step_id

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(errindication, None, None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], rejected
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == {"base": expected_error}
    assert entry.data == original_data

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], accepted
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    for key, value in expected_changes.items():
        assert entry.data[key] == value
    assert mock_setup_entry.called


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v3_is_checked_after_credentials(hass: HomeAssistant) -> None:
    """Test that a v3 flow is not aborted before its context name is known."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_VERSION: "3"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "v3"

    with patch(
        "homeassistant.components.snmp.config_flow.get_cmd",
        return_value=(None, None, None, [[OctetString("98F")]]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_CONTEXT_NAME: "other-context"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.1 (other-context)"
    assert result["data"][CONF_CONTEXT_NAME] == "other-context"


@pytest.mark.usefixtures("mock_walk_empty")
async def test_subentry_flow_reconfigure_invalid_oid(hass: HomeAssistant) -> None:
    """Test that reconfiguring to an OID pysnmp cannot resolve is rejected."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_BASEOID: "not_an_oid"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_BASEOID: "invalid_oid"}

    # A resolvable OID finishes the reconfigure
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
