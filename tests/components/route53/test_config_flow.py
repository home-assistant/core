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
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

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
        return_value=mock_boto3_client.return_value,
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
    "domain",
    [
        pytest.param("example.com", id="zone_apex"),
        pytest.param("EXAMPLE.COM.", id="case_and_trailing_dot"),
        pytest.param("home.example.com", id="subdomain_of_zone"),
    ],
)
async def test_domain_inside_zone_accepted(
    hass: HomeAssistant, mock_boto3_client: MagicMock, domain: str
) -> None:
    """Test domains belonging to the hosted zone are accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("notexample.com", id="suffix_near_miss"),
        pytest.param("other.org", id="outside_zone"),
    ],
)
async def test_domain_outside_zone_rejected(
    hass: HomeAssistant, mock_boto3_client: MagicMock, domain: str
) -> None:
    """Test domains outside the hosted zone are rejected and can be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DOMAIN: "invalid_domain"}

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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

    mock_boto3_client.return_value.get_hosted_zone.side_effect = side_effect

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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

    mock_boto3_client.return_value.get_hosted_zone.side_effect = None

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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
        return_value=mock_boto3_client.return_value,
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


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test import aborts if already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
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
        return_value=mock_boto3_client.return_value,
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
    mock_boto3_client.return_value.get_hosted_zone.side_effect = side_effect

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
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
        return_value=mock_boto3_client.return_value,
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
