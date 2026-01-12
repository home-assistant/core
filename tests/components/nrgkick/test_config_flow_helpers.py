"""Unit-style tests for NRGkick config flow helpers and defensive paths."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.nrgkick.api import NRGkickApiClientInvalidResponseError
from homeassistant.components.nrgkick.config_flow import _normalize_host, validate_input
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://example.com:1234/path", "example.com:1234"),
        ("https://example.com/path", "example.com:443"),
        ("example.com/some/path", "example.com"),
        ("192.168.1.10/", "192.168.1.10"),
    ],
)
def test_normalize_host(value: str, expected: str) -> None:
    """Test host normalization."""
    assert _normalize_host(value) == expected


@pytest.mark.parametrize("value", ["", "   "])
def test_normalize_host_empty(value: str) -> None:
    """Test host normalization with empty input."""
    with pytest.raises(vol.Invalid):
        _normalize_host(value)


def test_normalize_host_url_port_none_and_invalid_host() -> None:
    """Test URL normalization branches that are hard to hit with real parsers."""

    class _Url:
        host = "example.com"
        port = None

    with (
        patch("homeassistant.components.nrgkick.config_flow.cv.url", return_value="x"),
        patch(
            "homeassistant.components.nrgkick.config_flow.yarl.URL", return_value=_Url()
        ),
    ):
        assert _normalize_host("nrgkick://example.com/path") == "example.com"

    class _BadUrl:
        host = None
        port = None

    with (
        patch("homeassistant.components.nrgkick.config_flow.cv.url", return_value="x"),
        patch(
            "homeassistant.components.nrgkick.config_flow.yarl.URL",
            return_value=_BadUrl(),
        ),
        pytest.raises(vol.Invalid),
    ):
        _normalize_host("nrgkick://")


async def test_validate_input_fallback_name_and_serial_required(
    hass: HomeAssistant,
) -> None:
    """Test validate_input fallbacks and required fields."""
    api = AsyncMock()
    api.test_connection = AsyncMock(return_value=True)
    api.get_info = AsyncMock(return_value={"general": {"serial_number": "ABC"}})

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=api,
    ) as api_cls:
        info = await validate_input(hass, "192.168.1.100", username=None, password=None)

    assert info["title"] == "NRGkick"
    assert info["serial"] == "ABC"
    api_cls.assert_called_once_with(
        host="192.168.1.100",
        username=None,
        password=None,
        session=ANY,
    )

    api.get_info = AsyncMock(return_value={"general": {"device_name": "NRGkick"}})
    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=api,
        ),
        pytest.raises(NRGkickApiClientInvalidResponseError),
    ):
        await validate_input(hass, "192.168.1.100")
