"""Test the ntfy config flow."""

from unittest.mock import AsyncMock, patch

from aiontfy.exceptions import NtfyException, NtfyForbiddenAccessError, NtfyHTTPError
import pytest

from homeassistant.components.ntfy.const import CONF_TOPIC, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_aiontfy")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ntfy.config_flow.Ntfy.publish",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://ntfy.sh",
                CONF_TOPIC: "mytopic",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "mytopic"
    assert result["data"] == {
        CONF_URL: "https://ntfy.sh",
        CONF_TOPIC: "mytopic",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_aiontfy")
async def test_form_generate_topic(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_random: AsyncMock
) -> None:
    """Test random topic generation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.ntfy.config_flow.Ntfy.publish",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://ntfy.sh",
                CONF_TOPIC: "",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        mock_random.assert_called_once()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://ntfy.sh",
                CONF_TOPIC: "randomtopic",
            },
        )
        await hass.async_block_till_done()

    assert result["title"] == "randomtopic"
    assert result["data"] == {
        CONF_URL: "https://ntfy.sh",
        CONF_TOPIC: "randomtopic",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            NtfyHTTPError(418001, 418, "I'm a teapot", ""),
            "cannot_connect",
        ),
        (
            NtfyForbiddenAccessError(
                40301, 403, "forbidden", "https://ntfy.sh/docs/publish/#authentication"
            ),
            "forbidden_topic",
        ),
        (NtfyException, "cannot_connect"),
        (ValueError, "invalid_url"),
        (TypeError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aiontfy: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_aiontfy.publish.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://ntfy.sh",
            CONF_TOPIC: "mytopic",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_aiontfy.publish.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://ntfy.sh",
            CONF_TOPIC: "mytopic",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "mytopic"
    assert result["data"] == {
        CONF_URL: "https://ntfy.sh",
        CONF_TOPIC: "mytopic",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_aiontfy")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "https://ntfy.sh",
            CONF_TOPIC: "mytopic",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
