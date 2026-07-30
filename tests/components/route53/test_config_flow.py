"""Test the AWS Route53 config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions
import pytest

from homeassistant import config_entries
from homeassistant.components.route53.const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
)
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

YAML_CONFIG = {
    CONF_ACCESS_KEY_ID: "test-key",
    CONF_SECRET_ACCESS_KEY: "test-secret",
    CONF_ZONE: "test-zone",
    CONF_DOMAIN: "example.com",
    CONF_RECORDS: ["test1"],
    CONF_TTL: DEFAULT_TTL,
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_boto3_client: MagicMock
) -> None:
    """Test the full user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "example.com"
    assert result["data"] == {
        CONF_ACCESS_KEY_ID: "test-key",
        CONF_SECRET_ACCESS_KEY: "test-secret",
        CONF_ZONE: "test-zone",
        CONF_DOMAIN: "example.com",
        CONF_RECORDS: ["test1", "test2"],
        CONF_TTL: DEFAULT_TTL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "records",
    [
        pytest.param([], id="empty_list"),
        pytest.param([""], id="empty_string"),
        pytest.param(["   "], id="whitespace_only"),
    ],
)
async def test_records_must_not_be_empty(
    hass: HomeAssistant, mock_boto3_client: MagicMock, records: list[str]
) -> None:
    """Test a record list without usable entries is rejected and can be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.route53.config_flow.boto3.client",
            return_value=mock_boto3_client,
        ),
        pytest.raises(InvalidData) as err,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: records,
                CONF_TTL: DEFAULT_TTL,
            },
        )

    assert CONF_RECORDS in err.value.schema_errors
    assert not hass.config_entries.async_entries(DOMAIN)

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("EXAMPLE.COM.", id="case_and_trailing_dot"),
        pytest.param("example.com", id="exact"),
    ],
)
async def test_duplicate_domain_variants_abort(
    hass: HomeAssistant, mock_boto3_client: MagicMock, domain: str
) -> None:
    """Test case and trailing-dot variants are treated as the same entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-zone_example.com",
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: domain,
                CONF_RECORDS: ["test1"],
                CONF_TTL: DEFAULT_TTL,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_errors"),
    [
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidClientTokenId"}}, "Operation"
            ),
            {"base": "invalid_auth"},
            id="client_error",
        ),
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "NoSuchHostedZone"}}, "GetHostedZone"
            ),
            {CONF_ZONE: "invalid_zone"},
            id="no_such_hosted_zone",
        ),
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidInput"}}, "GetHostedZone"
            ),
            {CONF_ZONE: "invalid_zone"},
            id="invalid_input",
        ),
        pytest.param(
            botocore.exceptions.BotoCoreError(),
            {"base": "cannot_connect"},
            id="botocore_error",
        ),
        pytest.param(Exception, {"base": "unknown"}, id="unknown_error"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    side_effect: Exception,
    expected_errors: dict[str, str],
) -> None:
    """Test the user flow surfaces errors from AWS."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_boto3_client.get_hosted_zone.side_effect = side_effect

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors

    mock_boto3_client.get_hosted_zone.side_effect = None

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_boto3_client: MagicMock
) -> None:
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "example.com"
    assert result["data"] == {
        CONF_ACCESS_KEY_ID: "test-key",
        CONF_SECRET_ACCESS_KEY: "test-secret",
        CONF_ZONE: "test-zone",
        CONF_DOMAIN: "example.com",
        CONF_RECORDS: ["test1", "test2"],
        CONF_TTL: DEFAULT_TTL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_yaml_config_starts_the_import_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_boto3_client: MagicMock,
) -> None:
    """Test YAML configuration is imported into a config entry."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: YAML_CONFIG})
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_DOMAIN] == "example.com"
    assert entry.data[CONF_ZONE] == "test-zone"

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_boto3_client: MagicMock,
) -> None:
    """Test a failed YAML import raises a repair issue instead of an entry."""
    mock_boto3_client.get_hosted_zone.side_effect = Exception

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: YAML_CONFIG})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unknown"
    )


@pytest.mark.parametrize(
    "records",
    [
        pytest.param([], id="empty_list"),
        pytest.param([""], id="empty_string"),
        pytest.param(["  "], id="whitespace_only"),
    ],
)
async def test_import_flow_without_records_aborts(
    hass: HomeAssistant, mock_boto3_client: MagicMock, records: list[str]
) -> None:
    """Test YAML without usable records aborts instead of creating an entry."""
    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: records,
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_records"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_import_flow_strips_records(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test imported record names are stripped."""
    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: [" test1 ", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RECORDS] == ["test1", "test2"]


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test import aborts if already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-zone_example.com",
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1", "test2"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidClientTokenId"}}, "Operation"
            ),
            "invalid_auth",
            id="client_error",
        ),
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "NoSuchHostedZone"}}, "GetHostedZone"
            ),
            "invalid_zone",
            id="no_such_hosted_zone",
        ),
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidInput"}}, "GetHostedZone"
            ),
            "invalid_zone",
            id="invalid_input",
        ),
        pytest.param(
            botocore.exceptions.BotoCoreError(), "cannot_connect", id="botocore_error"
        ),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test import aborts with the matching reason when validation fails."""
    mock_boto3_client.get_hosted_zone.side_effect = side_effect

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "."],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test user flow aborts if already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-zone_example.com",
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1", "test2"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "test-zone",
                CONF_DOMAIN: "example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: DEFAULT_TTL,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
