"""Test the Ridwell config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aioridwell.errors import InvalidCredentialsError, RidwellError
import pytest

from homeassistant import config_entries
from homeassistant.components.ridwell.const import (
    CALENDAR_TITLE_ROTATING,
    CONF_CALENDAR_TITLE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        (InvalidCredentialsError, "invalid_auth"),
        (RidwellError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_aioridwell")
async def test_create_entry(
    hass: HomeAssistant,
    config: dict[str, Any],
    errors: str,
    side_effect: type[Exception],
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Test errors that can arise:
    with patch(
        "homeassistant.components.ridwell.config_flow.async_get_client",
        AsyncMock(side_effect=side_effect),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": errors}

    # Test that we can recover and finish the flow after errors occur:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


@pytest.mark.usefixtures("setup_config_entry")
async def test_duplicate_error(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test that errors are shown when duplicate entries are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_config_entry")
async def test_step_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test a full reauth flow."""
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new_password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data[CONF_PASSWORD] == "new_password"
    assert len(hass.config_entries.async_entries()) == 1


async def test_option_flow_event_title(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test option flow for event title."""

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CALENDAR_TITLE: CALENDAR_TITLE_ROTATING},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CALENDAR_TITLE] == CALENDAR_TITLE_ROTATING


@pytest.mark.usefixtures("mock_aioridwell")
async def test_successful_config_flow(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test the happy path of a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == config
