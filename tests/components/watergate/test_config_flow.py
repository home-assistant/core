"""Tests for the Watergate config flow."""

from collections.abc import Generator

import pytest
from pytest_homeassistant.common import AsyncMock, HomeAssistant, MockConfigEntry
from watergate_local_api import WatergateApiException
from watergate_local_api.models import DeviceState

from homeassistant.components.watergate.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    DEFAULT_DEVICE_STATE,
    DEFAULT_SERIAL_NUMBER,
    MOCK_CONFIG,
    MOCK_WEBHOOK_ID,
)


async def test_step_user_form(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_webhook_id_generation: Generator[None],
    user_input: dict[str, str],
) -> None:
    """Test checking if registration form works end to end."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_IP_ADDRESS in result["data_schema"].schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sonic"
    assert result["data"] == {**user_input, CONF_WEBHOOK_ID: MOCK_WEBHOOK_ID}
    assert result["result"].unique_id == DEFAULT_SERIAL_NUMBER


@pytest.mark.parametrize(
    "client_result",
    [AsyncMock(return_value=None), AsyncMock(side_effect=WatergateApiException)],
)
async def test_step_user_form_with_exception(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    user_input: dict[str, str],
    client_result: AsyncMock,
    mock_webhook_id_generation: Generator[None],
) -> None:
    """Test errors are displayed when checking device state throws."""
    mock_watergate_client.async_get_device_state = client_result

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_IP_ADDRESS] == "cannot_connect"

    mock_watergate_client.async_get_device_state = AsyncMock(
        return_value=DEFAULT_DEVICE_STATE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sonic"
    assert result["data"] == {**user_input, CONF_WEBHOOK_ID: MOCK_WEBHOOK_ID}


async def test_abort_if_id_is_not_unique(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test checking if we will inform user that this entity is already registered."""
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_IP_ADDRESS in result["data_schema"].schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test reconfiguring the IP address reloads the entry with the new host."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED

    result = await mock_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    (ip_key,) = result["data_schema"].schema
    assert ip_key.description == {"suggested_value": "http://localhost"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data[CONF_IP_ADDRESS] == user_input[CONF_IP_ADDRESS]
    assert mock_entry.data[CONF_WEBHOOK_ID] == MOCK_WEBHOOK_ID
    assert mock_entry.state is ConfigEntryState.LOADED
    # The reload re-ran setup, which registers the webhook URL on the device again.
    assert mock_watergate_client.async_set_webhook_url.await_count == 2


@pytest.mark.parametrize(
    "client_result",
    [AsyncMock(return_value=None), AsyncMock(side_effect=WatergateApiException)],
)
async def test_reconfigure_cannot_connect_then_success(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    user_input: dict[str, str],
    client_result: AsyncMock,
) -> None:
    """Test connection errors are shown and the flow recovers on retry."""
    mock_entry.add_to_hass(hass)
    mock_watergate_client.async_get_device_state = client_result

    result = await mock_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"][CONF_IP_ADDRESS] == "cannot_connect"

    mock_watergate_client.async_get_device_state = AsyncMock(
        return_value=DEFAULT_DEVICE_STATE
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data[CONF_IP_ADDRESS] == user_input[CONF_IP_ADDRESS]


async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test reconfiguring to a different physical device is refused."""
    mock_entry.add_to_hass(hass)
    other_state = DeviceState(
        "open",
        "on",
        True,
        True,
        "battery",
        "1.0.0",
        100,
        DEFAULT_DEVICE_STATE.water_meter,
        "another_serial",
    )
    mock_watergate_client.async_get_device_state = AsyncMock(return_value=other_state)

    result = await mock_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_entry.data[CONF_IP_ADDRESS] == MOCK_CONFIG[CONF_IP_ADDRESS]
