"""Test Discogs config flow."""

from unittest.mock import MagicMock, patch

import discogs_client
import pytest

from homeassistant.components.discogs.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_TOKEN, MOCK_USERNAME

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    mock_client = MagicMock()
    mock_client.identity.return_value.name = MOCK_USERNAME

    with (
        patch(
            "homeassistant.components.discogs.config_flow.discogs_client.Client",
            return_value=mock_client,
        ),
        patch("homeassistant.components.discogs.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == MOCK_USERNAME
        assert result["data"] == {CONF_TOKEN: MOCK_TOKEN}


async def test_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test flow with invalid token."""
    mock_client = MagicMock()
    mock_client.identity.side_effect = discogs_client.exceptions.HTTPError(
        "Unauthorized", 401
    )

    with patch(
        "homeassistant.components.discogs.config_flow.discogs_client.Client",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_TOKEN: "bad_token"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_auth"


async def test_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test flow with unexpected error."""
    mock_client = MagicMock()
    mock_client.identity.side_effect = RuntimeError("Something went wrong")

    with patch(
        "homeassistant.components.discogs.config_flow.discogs_client.Client",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (discogs_client.exceptions.HTTPError("Unauthorized", 401), "invalid_auth"),
        (RuntimeError("Something went wrong"), "unknown"),
    ],
)
async def test_flow_errors_then_success(
    hass: HomeAssistant, error: Exception, message: str
) -> None:
    """Test that errors can be recovered from."""
    mock_client = MagicMock()
    mock_client.identity.side_effect = error

    with patch(
        "homeassistant.components.discogs.config_flow.discogs_client.Client",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_TOKEN: "bad_token"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == message

    mock_client.identity.side_effect = None
    mock_client.identity.return_value.name = MOCK_USERNAME

    with (
        patch(
            "homeassistant.components.discogs.config_flow.discogs_client.Client",
            return_value=mock_client,
        ),
        patch("homeassistant.components.discogs.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Test flow aborts when account is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={CONF_TOKEN: MOCK_TOKEN},
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.identity.return_value.name = MOCK_USERNAME

    with patch(
        "homeassistant.components.discogs.config_flow.discogs_client.Client",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
