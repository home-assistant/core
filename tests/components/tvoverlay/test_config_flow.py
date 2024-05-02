"""Test TvOverlay config flow."""

from unittest.mock import AsyncMock

import pytest
from tvoverlay.exceptions import ConnectError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tvoverlay.const import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import (
    CONF_CONFIG_FLOW,
    CONF_DEFAULT_FLOW,
    DEFAULT_NAME,
    HOST,
    NAME,
    mocked_tvoverlay_info,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (AsyncMock(side_effect=ConnectError), "cannot_connect"),
        (AsyncMock(side_effect=Exception), "unknown"),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    side_effect,
    error_message,
) -> None:
    """Test user initialized flow with errors."""
    with mocked_tvoverlay_info() as tvmock:
        tvmock.side_effect = side_effect
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_message}


@pytest.mark.parametrize(
    (
        "user_input",
        "expected_type",
        "expected_title",
        "expected_data",
        "expected_reason",
    ),
    [
        (
            CONF_CONFIG_FLOW,
            data_entry_flow.FlowResultType.CREATE_ENTRY,
            NAME,
            CONF_CONFIG_FLOW,
            None,
        ),
        (
            CONF_DEFAULT_FLOW,
            data_entry_flow.FlowResultType.CREATE_ENTRY,
            DEFAULT_NAME,
            CONF_DEFAULT_FLOW,
            None,
        ),
        (
            CONF_CONFIG_FLOW,
            data_entry_flow.FlowResultType.ABORT,
            None,
            None,
            "already_configured",
        ),
    ],
)
async def test_tvoverlay_config_flow(
    hass: HomeAssistant,
    user_input,
    expected_type,
    expected_title,
    expected_data,
    expected_reason,
) -> None:
    """Test TvOverlay config flow."""
    if expected_reason == "already_configured":
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_CONFIG_FLOW,
            unique_id=HOST,
        )
        entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    if user_input:
        with mocked_tvoverlay_info(user_input.get(CONF_NAME)):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=user_input,
            )

    result_type = result.get("type", None)
    assert result_type == expected_type
    if expected_title:
        result_title = result.get("title", None)
        assert result_title == expected_title
    if expected_data:
        result_data = result.get("data", None)
        assert result_data == expected_data
    if expected_reason:
        result_reason = result.get("reason", None)
        assert result_reason == expected_reason
