"""Tests for the SleepIQ config flow."""

from unittest.mock import AsyncMock, patch

from asyncsleepiq import (
    SleepIQConnectionException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from .conftest import SLEEPIQ_CONFIG, setup_platform

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_import(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Test that we can import a config entry."""
    with patch("asyncsleepiq.AsyncSleepIQ.login"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
    assert entry.data[CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "SleepIQ",
    }


async def test_import_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test importing an already configured account raises the YAML issue."""
    entry = await setup_platform(hass)

    with patch("asyncsleepiq.AsyncSleepIQ.login") as mock_login:
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    mock_login.assert_not_called()
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(SleepIQLoginException, "invalid_auth", id="invalid_auth"),
        pytest.param(
            SleepIQConnectionException, "cannot_connect", id="connection_error"
        ),
        pytest.param(SleepIQTimeoutException, "cannot_connect", id="timeout"),
    ],
)
async def test_import_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test that a failed import raises an import issue instead of the YAML one."""
    with patch(
        "asyncsleepiq.AsyncSleepIQ.login",
        side_effect=side_effect,
    ):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_key == f"deprecated_yaml_import_issue_{reason}"
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    with patch("asyncsleepiq.AsyncSleepIQ.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (SleepIQLoginException, "invalid_auth"),
        (SleepIQTimeoutException, "cannot_connect"),
    ],
)
async def test_login_failure(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test that we show user form with appropriate error on login failure."""
    with patch(
        "asyncsleepiq.AsyncSleepIQ.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=SLEEPIQ_CONFIG
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error}

    with patch("asyncsleepiq.AsyncSleepIQ.login", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=SLEEPIQ_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow provides entry creation data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch("asyncsleepiq.AsyncSleepIQ.login", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], SLEEPIQ_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
    assert result2["data"][CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]
    assert result2["result"].unique_id == SLEEPIQ_CONFIG[CONF_USERNAME].lower()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_password(hass: HomeAssistant) -> None:
    """Test reauth form."""

    # set up initially
    entry = await setup_platform(hass)
    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.sleepiq.config_flow.AsyncSleepIQ.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
