"""Test the Tessie config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    TEST_CONFIG,
    TEST_STATE_OF_ALL_VEHICLES,
    error_auth,
    error_connection,
    error_unknown,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_config_flow_get_state_of_all_vehicles():
    """Mock get_state_of_all_vehicles in config flow."""
    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        return_value=TEST_STATE_OF_ALL_VEHICLES,
    ) as mock_config_flow_get_state_of_all_vehicles:
        yield mock_config_flow_get_state_of_all_vehicles


@pytest.fixture(autouse=True)
def mock_async_setup_entry():
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.tessie.async_setup_entry",
        return_value=True,
    ) as mock_async_setup_entry:
        yield mock_async_setup_entry


async def test_form(
    hass: HomeAssistant,
    mock_config_flow_get_state_of_all_vehicles,
    mock_async_setup_entry,
) -> None:
    """Test we get the form."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )
    await hass.async_block_till_done()
    assert len(mock_async_setup_entry.mock_calls) == 1
    assert len(mock_config_flow_get_state_of_all_vehicles.mock_calls) == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Tessie"
    assert result2["data"] == TEST_CONFIG


async def test_abort(
    hass: HomeAssistant,
    mock_config_flow_get_state_of_all_vehicles,
    mock_async_setup_entry,
) -> None:
    """Test a duplicate entry aborts."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (error_auth(), {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (error_unknown(), {"base": "unknown"}),
        (error_connection(), {"base": "cannot_connect"}),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, side_effect, error, mock_config_flow_get_state_of_all_vehicles
) -> None:
    """Test errors are handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_config_flow_get_state_of_all_vehicles.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_config_flow_get_state_of_all_vehicles.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        TEST_CONFIG,
    )
    assert "errors" not in result3
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(
    hass: HomeAssistant,
    mock_config_flow_get_state_of_all_vehicles,
    mock_async_setup_entry,
) -> None:
    """Test reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result1 = await mock_entry.start_reauth_flow(hass)

    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "reauth_confirm"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )
    await hass.async_block_till_done()
    assert len(mock_async_setup_entry.mock_calls) == 1
    assert len(mock_config_flow_get_state_of_all_vehicles.mock_calls) == 1

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == TEST_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (error_auth(), {CONF_ACCESS_TOKEN: "invalid_access_token"}),
        (error_unknown(), {"base": "unknown"}),
        (error_connection(), {"base": "cannot_connect"}),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_flow_get_state_of_all_vehicles,
    mock_async_setup_entry,
    side_effect,
    error,
) -> None:
    """Test reauth flows that fail."""

    mock_config_flow_get_state_of_all_vehicles.side_effect = side_effect

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result1 = await mock_entry.start_reauth_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Complete the flow
    mock_config_flow_get_state_of_all_vehicles.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        TEST_CONFIG,
    )
    assert "errors" not in result3
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert mock_entry.data == TEST_CONFIG
    assert len(mock_async_setup_entry.mock_calls) == 1
