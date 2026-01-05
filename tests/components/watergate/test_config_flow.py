"""Tests for the Watergate config flow."""

from collections.abc import Generator

import pytest
from watergate_local_api import WatergateApiException

from homeassistant.components.watergate.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import FlowResultType

from .const import DEFAULT_DEVICE_STATE, DEFAULT_SERIAL_NUMBER, MOCK_WEBHOOK_ID

from tests.common import AsyncMock, HomeAssistant, MockConfigEntry


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
    """Test checking if errors will be displayed when Exception is thrown while checking device state."""
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
