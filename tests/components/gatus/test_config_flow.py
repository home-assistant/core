"""Test the Gatus config flow."""

from types import TracebackType
from typing import Any, Self
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


class FakeResponse:
    """Fake response class to reliably simulate aiohttp client responses."""

    def __init__(self, status: int, json_data: Any) -> None:
        """Initialize fake response."""
        self.status = status
        self._json_data = json_data

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager."""

    async def json(self) -> Any:
        """Return fake json data."""
        return self._json_data


async def test_form_success(hass: HomeAssistant) -> None:
    """Test we get the form and a successful entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Mock validation and block integration setup from running in the background
    with (
        patch(
            "homeassistant.components.gatus.config_flow.async_get_clientsession"
        ) as mock_get_session,
        patch(
            "homeassistant.components.gatus.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        mock_session = MagicMock()
        mock_session.get.return_value = FakeResponse(200, [{"key": "test-endpoint"}])
        mock_get_session.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Gatus"
    assert result2["data"] == {
        CONF_URL: "http://gatus.local:8080",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (aiohttp.ClientError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
    ],
)
async def test_form_connection_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Test we handle various network connection errors gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.async_get_clientsession"
    ) as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.side_effect = side_effect
        mock_get_session.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}


async def test_form_invalid_status_code(hass: HomeAssistant) -> None:
    """Test we handle a non-200 HTTP status code gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.async_get_clientsession"
    ) as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = FakeResponse(404, {})
        mock_get_session.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle arbitrary unexpected exceptions gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.gatus.config_flow.validate_input",
        side_effect=Exception("Unexpected breakdown"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://gatus.local:8080"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that duplicate configurations for the same URL abort early."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local:8080"},
        unique_id="gatus_instance",
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.local:8080"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
