"""Test user-flow recovery, duplicate detection, and reauthentication."""

import asyncio
from unittest.mock import AsyncMock

from aiokoito import (
    KoitoAuthenticationError,
    KoitoConnectionError,
    KoitoResponseError,
    Summary,
)
import pytest

from homeassistant.components.koito.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations

from tests.common import MockConfigEntry

INPUT = {"url": "https://koito.example", "api_key": "key"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Create a normalized configuration through the flow manager."""
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert form["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(form["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result["title"] == "koito.example"
    assert result["data"] == INPUT


@pytest.mark.parametrize(
    "url",
    [
        "invalid",
        "http://[",
        "http://example.test:bad",
        "https://user:password@example.test",
        "https://example.test?query=1",
        "https://example.test#fragment",
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_invalid_url_recovers(hass: HomeAssistant, url: str) -> None:
    """Recover from invalid connection input."""
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    error = await hass.config_entries.flow.async_configure(
        form["flow_id"], {**INPUT, "url": url}
    )
    assert error["errors"] == {"base": "invalid_url"}
    result = await hass.config_entries.flow.async_configure(form["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://koito.example:443/", "https://koito.example"),
        ("http://koito.example:80/", "http://koito.example"),
        ("http://[::1]:8484/", "http://[::1]:8484"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_normalization(hass: HomeAssistant, url: str, expected: str) -> None:
    """Normalize IPv6, default ports, and trailing slashes."""
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {**INPUT, "url": url}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["url"] == expected


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (KoitoAuthenticationError(), "invalid_auth"),
        (KoitoConnectionError(), "cannot_connect"),
        (KoitoResponseError(), "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_error_recovery(
    hass: HomeAssistant, mock_client: AsyncMock, failure: Exception, error: str
) -> None:
    """Finish setup after each supported protocol failure."""
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_client.async_get_summary.side_effect = failure
    result = await hass.config_entries.flow.async_configure(form["flow_id"], INPUT)
    assert result["errors"] == {"base": error}
    mock_client.async_get_summary.side_effect = None
    result = await hass.config_entries.flow.async_configure(form["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client")
async def test_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reject an already configured server."""
    mock_config_entry.add_to_hass(hass)
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(form["flow_id"], INPUT)
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (KoitoAuthenticationError(), "invalid_auth"),
        (KoitoConnectionError(), "cannot_connect"),
        (KoitoResponseError(), "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    failure: Exception,
    error: str,
) -> None:
    """Replace credentials on the existing entry after an error."""
    mock_config_entry.add_to_hass(hass)
    form = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    mock_client.async_get_summary.side_effect = failure
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"api_key": "new-key"}
    )
    assert result["errors"] == {"base": error}
    mock_client.async_get_summary.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"api_key": "new-key"}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert result["translation_domain"] == "homeassistant"
    translations = await async_get_translations(hass, "en", "config", {"homeassistant"})
    assert translations.get(f"component.homeassistant.config.abort.{result['reason']}")
    assert mock_config_entry.data["api_key"] == "new-key"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_concurrent_duplicate(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Prevent duplicate entries across concurrent user flows."""
    ready = asyncio.Event()
    count = 0
    good = mock_client.async_get_summary.return_value

    async def validate(*args: object) -> Summary:
        nonlocal count
        count += 1
        if count == 2:
            ready.set()
        await ready.wait()
        return good

    mock_client.async_get_summary.side_effect = validate
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    results = await asyncio.gather(
        hass.config_entries.flow.async_configure(first["flow_id"], INPUT),
        hass.config_entries.flow.async_configure(second["flow_id"], INPUT),
    )
    assert {result["type"] for result in results} == {
        FlowResultType.CREATE_ENTRY,
        FlowResultType.ABORT,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
