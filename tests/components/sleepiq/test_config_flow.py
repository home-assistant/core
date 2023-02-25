"""Tests for the SleepIQ config flow."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from asyncsleepiq import SleepIQLoginException, SleepIQTimeoutException
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import SLEEPIQ_CONFIG, setup_platform


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sleepiq.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_import(hass: HomeAssistant) -> None:
    """Test that we can import a config entry."""
    with patch("asyncsleepiq.AsyncSleepIQ.login"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
    assert entry.data[CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]


@pytest.mark.parametrize(
    "side_effect", [SleepIQLoginException, SleepIQTimeoutException]
)
async def test_import_failure(hass: HomeAssistant, side_effect) -> None:
    """Test that we won't import a config entry on login failure."""
    with patch(
        "asyncsleepiq.AsyncSleepIQ.login",
        side_effect=side_effect,
    ):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    with patch("asyncsleepiq.AsyncSleepIQ.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (SleepIQLoginException, "invalid_auth"),
        (SleepIQTimeoutException, "cannot_connect"),
    ],
)
async def test_login_failure(hass: HomeAssistant, side_effect, error) -> None:
    """Test that we show user form with appropriate error on login failure."""
    with patch(
        "asyncsleepiq.AsyncSleepIQ.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=SLEEPIQ_CONFIG
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error}


async def test_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow provides entry creation data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("asyncsleepiq.AsyncSleepIQ.login", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], SLEEPIQ_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
    assert result2["data"][CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_password(hass: HomeAssistant) -> None:
    """Test reauth form."""

    # set up initially
    entry = await setup_platform(hass)
    with patch(
        "homeassistant.components.sleepiq.config_flow.AsyncSleepIQ.login",
        side_effect=SleepIQLoginException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=entry.data,
        )

    with patch(
        "homeassistant.components.sleepiq.config_flow.AsyncSleepIQ.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
