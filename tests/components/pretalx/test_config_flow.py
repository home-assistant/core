"""Test the pretalx config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.pretalx.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EVENT, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BASE_URL

from tests.common import MockConfigEntry, async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

USER_INPUT = {CONF_URL: "https://pretalx.com", CONF_EVENT: "democon"}


async def test_full_flow(
    hass: HomeAssistant, mock_pretalx: None, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DemoCon"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "https://pretalx.com_democon"


async def test_url_trailing_slash_is_stripped(
    hass: HomeAssistant, mock_pretalx: None, mock_setup_entry: AsyncMock
) -> None:
    """Test that a trailing slash in the URL is removed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://pretalx.com/", CONF_EVENT: "democon"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("status", "exc", "error"),
    [
        (404, None, "event_not_found"),
        (500, None, "cannot_connect"),
        (None, ClientError, "cannot_connect"),
    ],
)
async def test_form_errors_then_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    status: int | None,
    exc: type[Exception] | None,
    error: str,
) -> None:
    """Test that errors are shown and the flow can recover."""
    if exc is not None:
        aioclient_mock.get(f"{BASE_URL}/", exc=exc)
    else:
        aioclient_mock.get(f"{BASE_URL}/", status=status)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}/",
        json=await async_load_json_object_fixture(hass, "event.json", DOMAIN),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DemoCon"


async def test_already_configured(
    hass: HomeAssistant,
    mock_pretalx: None,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that configuring the same event twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
