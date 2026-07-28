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


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_boto3_client: MagicMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "example.com"
    assert result2["data"] == {
        CONF_ACCESS_KEY_ID: "test-key",
        CONF_SECRET_ACCESS_KEY: "test-secret",
        CONF_ZONE: "test-zone",
        CONF_DOMAIN: "example.com",
        CONF_RECORDS: ["test1", "test2"],
        CONF_TTL: DEFAULT_TTL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidClientTokenId"}}, "Operation"
            ),
            "invalid_auth",
            id="client_error",
        ),
        pytest.param(
            botocore.exceptions.BotoCoreError(), "invalid_auth", id="botocore_error"
        ),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    side_effect: Exception,
    error: str,
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
        result2 = await hass.config_entries.flow.async_configure(
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

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


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
            botocore.exceptions.BotoCoreError(), "invalid_auth", id="botocore_error"
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


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test reconfiguring an existing entry updates its data and title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="example.com",
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

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "new-key",
                CONF_SECRET_ACCESS_KEY: "new-secret",
                CONF_ZONE: "new-zone",
                CONF_DOMAIN: "new.example.com",
                CONF_RECORDS: ["test1", "test2"],
                CONF_TTL: 600,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "new.example.com"
    assert entry.data == {
        CONF_ACCESS_KEY_ID: "new-key",
        CONF_SECRET_ACCESS_KEY: "new-secret",
        CONF_ZONE: "new-zone",
        CONF_DOMAIN: "new.example.com",
        CONF_RECORDS: ["test1", "test2"],
        CONF_TTL: 600,
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "InvalidClientTokenId"}}, "Operation"
            ),
            "invalid_auth",
            id="client_error",
        ),
        pytest.param(
            botocore.exceptions.BotoCoreError(), "invalid_auth", id="botocore_error"
        ),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the reconfigure flow surfaces errors and leaves the entry unchanged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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

    result = await entry.start_reconfigure_flow(hass)

    mock_boto3_client.return_value.get_hosted_zone.side_effect = side_effect

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "new-key",
                CONF_SECRET_ACCESS_KEY: "new-secret",
                CONF_ZONE: "new-zone",
                CONF_DOMAIN: "new.example.com",
                CONF_RECORDS: ["test1"],
                CONF_TTL: DEFAULT_TTL,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}
    assert entry.data[CONF_ZONE] == "test-zone"


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, mock_boto3_client: MagicMock
) -> None:
    """Test reconfigure aborts when the new values match another entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "other-key",
            CONF_SECRET_ACCESS_KEY: "other-secret",
            CONF_ZONE: "other-zone",
            CONF_DOMAIN: "other.example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    other_entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_KEY_ID: "test-key",
                CONF_SECRET_ACCESS_KEY: "test-secret",
                CONF_ZONE: "other-zone",
                CONF_DOMAIN: "other.example.com",
                CONF_RECORDS: ["test1"],
                CONF_TTL: DEFAULT_TTL,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
        result2 = await hass.config_entries.flow.async_configure(
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

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
