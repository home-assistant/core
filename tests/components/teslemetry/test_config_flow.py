"""Test the Teslemetry config flow."""

from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)

from homeassistant import config_entries
from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG

from tests.common import MockConfigEntry

BAD_CONFIG = {CONF_ACCESS_TOKEN: "bad_access_token"}


@pytest.fixture(autouse=True)
def mock_test():
    """Mock Teslemetry api class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.test", return_value=True
    ) as mock_test:
        yield mock_test


async def test_form(
    hass: HomeAssistant,
) -> None:
    """Test we get the form."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert not result1["errors"]

    with patch(
        "homeassistant.components.teslemetry.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (InvalidToken, {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (SubscriptionRequired, {"base": "subscription_required"}),
        (ClientConnectionError, {"base": "cannot_connect"}),
        (TeslaFleetError, {"base": "unknown"}),
    ],
)
async def test_form_errors(hass: HomeAssistant, side_effect, error, mock_test) -> None:
    """Test errors are handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_test.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_test.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        CONFIG,
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant, mock_test) -> None:
    """Test reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=BAD_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=BAD_CONFIG,
    )

    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "reauth_confirm"
    assert not result1["errors"]

    with patch(
        "homeassistant.components.teslemetry.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
        assert len(mock_test.mock_calls) == 1

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (InvalidToken, {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (SubscriptionRequired, {"base": "subscription_required"}),
        (ClientConnectionError, {"base": "cannot_connect"}),
        (TeslaFleetError, {"base": "unknown"}),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, mock_test, side_effect, error
) -> None:
    """Test reauth flows that fail."""

    # Start the reauth
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=BAD_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=BAD_CONFIG,
    )

    mock_test.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BAD_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_test.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        CONFIG,
    )
    assert "errors" not in result3
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert mock_entry.data == CONFIG
