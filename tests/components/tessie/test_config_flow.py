"""Test the Tessie config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_CONFIG,
    setup_platform,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_get_state_of_all_vehicles) -> None:
    """Test we get the form."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert not result1["errors"]

    with patch(
        "homeassistant.components.tessie.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
        assert len(mock_get_state_of_all_vehicles.mock_calls) == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Tessie"
    assert result2["data"] == TEST_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ERROR_AUTH, {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (ERROR_UNKNOWN, {"base": "unknown"}),
        (ERROR_CONNECTION, {"base": "cannot_connect"}),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, side_effect, error, mock_get_state_of_all_vehicles
) -> None:
    """Test errors are handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_get_state_of_all_vehicles.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_get_state_of_all_vehicles.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        TEST_CONFIG,
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant, mock_get_state_of_all_vehicles) -> None:
    """Test reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_CONFIG,
    )

    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "reauth_confirm"
    assert not result1["errors"]

    with patch(
        "homeassistant.components.tessie.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
        assert len(mock_get_state_of_all_vehicles.mock_calls) == 1

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == TEST_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ERROR_AUTH, {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (ERROR_UNKNOWN, {"base": "unknown"}),
        (ERROR_CONNECTION, {"base": "cannot_connect"}),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, mock_get_state_of_all_vehicles, side_effect, error
) -> None:
    """Test reauth flows that fail."""

    mock_entry = await setup_platform(hass, [Platform.BINARY_SENSOR])
    mock_get_state_of_all_vehicles.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_CONFIG,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_get_state_of_all_vehicles.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        TEST_CONFIG,
    )
    assert "errors" not in result3
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert mock_entry.data == TEST_CONFIG
