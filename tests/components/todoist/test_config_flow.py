"""Test the todoist config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.todoist.const import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TOKEN

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
async def patch_api(
    api: AsyncMock,
) -> None:
    """Mock setup of the todoist integration."""
    with patch(
        "homeassistant.components.todoist.config_flow.TodoistAPIAsync", return_value=api
    ):
        yield


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: TOKEN,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Todoist"
    assert result2.get("data") == {
        CONF_TOKEN: TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("todoist_api_status", [HTTPStatus.UNAUTHORIZED])
async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: TOKEN,
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "invalid_access_token"}


@pytest.mark.parametrize("todoist_api_status", [HTTPStatus.INTERNAL_SERVER_ERROR])
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: TOKEN,
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}


@pytest.mark.parametrize("todoist_api_status", [HTTPStatus.UNAUTHORIZED])
async def test_unknown_error(hass: HomeAssistant, api: AsyncMock) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    api.get_tasks.side_effect = ValueError("unexpected")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: TOKEN,
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant, setup_integration: None) -> None:
    """Test that only a single instance can be configured."""

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"
