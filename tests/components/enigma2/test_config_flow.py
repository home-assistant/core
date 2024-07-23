"""Test the Enigma2 config flow."""

from typing import Any
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from openwebif.error import InvalidAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.issue_registry import IssueRegistry

from .conftest import (
    EXPECTED_OPTIONS,
    TEST_FULL,
    TEST_IMPORT_FULL,
    TEST_IMPORT_REQUIRED,
    TEST_REQUIRED,
    MockDevice,
)


@pytest.fixture
async def user_flow(hass: HomeAssistant) -> str:
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    return result["flow_id"]


@pytest.mark.parametrize(
    ("test_config"),
    [(TEST_FULL), (TEST_REQUIRED)],
)
async def test_form_user(
    hass: HomeAssistant, user_flow: str, test_config: dict[str, Any]
):
    """Test a successful user initiated flow."""
    with (
        patch(
            "openwebif.api.OpenWebIfDevice.__new__",
            return_value=MockDevice(),
        ),
        patch(
            "homeassistant.components.enigma2.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, test_config)
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == test_config[CONF_HOST]
    assert result["data"] == test_config

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_user_errors(
    hass: HomeAssistant, user_flow, exception: Exception, error_type: str
) -> None:
    """Test we handle errors."""
    with patch(
        "homeassistant.components.enigma2.config_flow.OpenWebIfDevice.__new__",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"] == {"base": error_type}


@pytest.mark.parametrize(
    ("test_config", "expected_data", "expected_options"),
    [
        (TEST_IMPORT_FULL, TEST_FULL, EXPECTED_OPTIONS),
        (TEST_IMPORT_REQUIRED, TEST_REQUIRED, {}),
    ],
)
async def test_form_import(
    hass: HomeAssistant,
    test_config: dict[str, Any],
    expected_data: dict[str, Any],
    expected_options: dict[str, Any],
    issue_registry: IssueRegistry,
) -> None:
    """Test we get the form with import source."""
    with (
        patch(
            "homeassistant.components.enigma2.config_flow.OpenWebIfDevice.__new__",
            return_value=MockDevice(),
        ),
        patch(
            "homeassistant.components.enigma2.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=test_config,
        )
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )

    assert issue
    assert issue.issue_domain == DOMAIN
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == test_config[CONF_HOST]
    assert result["data"] == expected_data
    assert result["options"] == expected_options

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_import_errors(
    hass: HomeAssistant,
    exception: Exception,
    error_type: str,
    issue_registry: IssueRegistry,
) -> None:
    """Test we handle errors on import."""
    with patch(
        "homeassistant.components.enigma2.config_flow.OpenWebIfDevice.__new__",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_{DOMAIN}_import_issue_{error_type}"
    )

    assert issue
    assert issue.issue_domain == DOMAIN
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_type
