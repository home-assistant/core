"""Tests for the TFA.me integration: test of data.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from tfa_me_ha_local.client import (
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.components.tfa_me.data import TFAmeUniqueID
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_get_identifier_success_ip(hass: HomeAssistant) -> None:
    """Test get_identifier() for a normal IP address returns gateway_id."""

    with patch("homeassistant.components.tfa_me.data.TFAmeClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_sensors = AsyncMock(
            return_value={"gateway_id": "012345678"}
        )

        data = TFAmeUniqueID(hass, "192.168.1.10")
        identifier = await data.get_identifier()

        # Check returned identifier
        assert identifier == "012345678"

        # Ensure the client was constructed with the plain host (IP)
        mock_client_cls.assert_called_once()
        args, _ = mock_client_cls.call_args
        # args: (host, "sensors", log_level, session)
        assert args[0] == "192.168.1.10"
        assert args[1] == "sensors"


@pytest.mark.asyncio
async def test_get_identifier_success_station_id(hass: HomeAssistant) -> None:
    """Test get_identifier() when user passes station ID (host with '-')."""

    with patch("homeassistant.components.tfa_me.data.TFAmeClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_sensors = AsyncMock(
            return_value={"gateway_id": "012345678"}
        )

        # User inputs a station ID in format "XXX-XXX-XXX"
        data = TFAmeUniqueID(hass, "012-345-678")
        identifier = await data.get_identifier()

        assert identifier == "012345678"

        # Host should have been resolved to mDNS
        mock_client_cls.assert_called_once()
        args, _ = mock_client_cls.call_args
        assert args[0] == "tfa-me-012-345-678.local"
        assert args[1] == "sensors"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("side_effect", "return_value", "expected_exception", "expected_text"),
    [
        (TFAmeHTTPError("bad json"), None, TFAmeHTTPError, "bad json"),
        (TFAmeJSONError("bad json"), None, TFAmeJSONError, "bad json"),
        (TFAmeTimeoutError("timeout"), None, TFAmeTimeoutError, "timeout"),
        (
            TFAmeConnectionError("connection failed"),
            None,
            TFAmeConnectionError,
            "connection failed",
        ),
        (ValueError("boom"), None, TFAmeException, "unknown"),
        (None, {}, TFAmeException, "missing_identifier"),
    ],
    ids=[
        "http-error-invalid-response",
        "json-error-invalid-response",
        "timeout-cannot-connect",
        "connection-error-cannot-connect",
        "unexpected-error-unknown",
        "missing-identifier",
    ],
)
async def test_get_identifier_error_mapping(
    hass: HomeAssistant,
    side_effect: Exception | None,
    return_value: dict | None,
    expected_exception: type[Exception],
    expected_text: str,
) -> None:
    """Test get_identifier() preserves client errors and maps unknown errors."""

    with patch("homeassistant.components.tfa_me.data.TFAmeClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value

        if side_effect is not None:
            mock_client.async_get_sensors = AsyncMock(side_effect=side_effect)
        else:
            mock_client.async_get_sensors = AsyncMock(return_value=return_value)

        data = TFAmeUniqueID(hass, "192.168.1.10")

        with pytest.raises(expected_exception) as excinfo:
            await data.get_identifier()

        assert expected_text in str(excinfo.value)
