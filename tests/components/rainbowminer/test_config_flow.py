"""Test the RainbowMiner config flow."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from rainbowminer_api_client import (
    RainbowMinerAuthError,
    RainbowMinerConnectionError,
    Status,
)

from homeassistant import config_entries
from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST, TEST_PORT, VALID_STATUS

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _user_input(**overrides: str | int) -> dict[str, str | int]:
    """Return a minimal valid user input."""
    data: dict[str, str | int] = {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    data.update(overrides)
    return data


async def test_form(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"RainbowMiner {TEST_HOST}:{TEST_PORT}"
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_auth(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form with username and password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _user_input(
            username="test-user",
            password="test-pass",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "test-user"
    assert result["data"][CONF_PASSWORD] == "test-pass"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_rainbowminer_client.get_status.side_effect = RainbowMinerAuthError(
        "Unauthorized"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_rainbowminer_client.get_status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_rainbowminer_client.get_status.side_effect = RainbowMinerConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_rainbowminer_client.get_status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_duplicate_during_validation(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
) -> None:
    """Test a duplicate flow aborts when another flow created an entry meanwhile."""
    validation_started = asyncio.Event()
    validation_continue = asyncio.Event()

    async def _slow_get_status() -> Status:
        validation_started.set()
        await validation_continue.wait()
        return VALID_STATUS

    mock_rainbowminer_client.get_status.side_effect = _slow_get_status

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Park the first flow inside validation.
    flow1_task = asyncio.create_task(
        hass.config_entries.flow.async_configure(result1["flow_id"], _user_input())
    )
    await validation_started.wait()

    # The second flow passes its first check and creates an entry meanwhile.
    validation_continue.set()
    result = await hass.config_entries.flow.async_configure(
        result2["flow_id"], _user_input()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # The first flow passed its first check but must abort on the recheck.
    flow1_result = await flow1_task
    assert flow1_result["type"] is FlowResultType.ABORT
    assert flow1_result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
