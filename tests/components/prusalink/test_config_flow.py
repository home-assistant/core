"""Test the PrusaLink config flow."""
import asyncio
from unittest.mock import patch

from spencerassistant import config_entries
from spencerassistant.components.prusalink.config_flow import InvalidAuth
from spencerassistant.components.prusalink.const import DOMAIN
from spencerassistant.core import spencerAssistant
from spencerassistant.data_entry_flow import FlowResultType


async def test_form(hass: spencerAssistant, mock_version_api) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "spencerassistant.components.prusalink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://1.1.1.1/",
                "api_key": "abcdefg",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "PrusaMINI"
    assert result2["data"] == {
        "host": "http://1.1.1.1",
        "api_key": "abcdefg",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: spencerAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "spencerassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abcdefg",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown(hass: spencerAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "spencerassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abcdefg",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_too_low_version(hass: spencerAssistant, mock_version_api) -> None:
    """Test we handle too low API version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "1.2.0"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "api_key": "abcdefg",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "not_supported"}


async def test_form_invalid_version_2(hass: spencerAssistant, mock_version_api) -> None:
    """Test we handle invalid version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "i am not a version"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "api_key": "abcdefg",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "not_supported"}


async def test_form_cannot_connect(hass: spencerAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "spencerassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abcdefg",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
