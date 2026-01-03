"""Unit-style tests for NRGkick config flow helpers and defensive paths."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import NRGkickApiClientCommunicationError
from homeassistant.components.nrgkick.config_flow import (
    NRGkickConfigFlow,
    _normalize_host,
    validate_input,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
        pytest.raises(ValueError),
    ):
        await validate_input(hass, "192.168.1.100")


async def test_flow_guards_and_fallbacks(hass: HomeAssistant) -> None:
    """Test defensive guards and fallbacks that are hard to hit via FlowManager."""
    flow = NRGkickConfigFlow()
    flow.hass = hass

    # user_auth without pending host falls back to user step
    flow._pending_host = None
    result = await flow.async_step_user_auth()
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    # reauth_confirm without entry_id aborts
    flow.context = {"source": config_entries.SOURCE_REAUTH}
    result = await flow.async_step_reauth_confirm()
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "reauth_failed"

    # reauth_confirm with missing entry aborts
    flow.context = {
        "source": config_entries.SOURCE_REAUTH,
        "entry_id": "does-not-exist",
    }
    result = await flow.async_step_reauth_confirm()
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "reauth_failed"

    # reconfigure_confirm without entry_id aborts
    flow.context = {"source": config_entries.SOURCE_RECONFIGURE}
    result = await flow.async_step_reconfigure_confirm()
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_failed"


async def test_reauth_confirm_shows_form_and_placeholders(hass: HomeAssistant) -> None:
    """Test reauth confirm form placeholders."""
    entry = MockConfigEntry(domain="nrgkick", data={CONF_HOST: "http://example.com"})
    entry.add_to_hass(hass)

    flow = NRGkickConfigFlow()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}

    result = await flow.async_step_reauth_confirm()
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    placeholders = result.get("description_placeholders")
    assert placeholders is not None
    assert placeholders["host"] == "http://example.com"
    assert placeholders["device_ip"] == "example.com:80"


async def test_reconfigure_confirm_error_uses_user_input_device_ip(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reconfigure_confirm placeholder uses submitted host on error."""
    entry = MockConfigEntry(domain="nrgkick", data={CONF_HOST: "192.168.1.1"})
    entry.add_to_hass(hass)

    flow = NRGkickConfigFlow()
    flow.hass = hass
    flow.context = {
        "source": config_entries.SOURCE_RECONFIGURE,
        "entry_id": entry.entry_id,
    }

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result = await flow.async_step_reconfigure_confirm({CONF_HOST: "192.168.1.200"})

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "reconfigure_confirm"
    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("description_placeholders") == {
        "host": "192.168.1.1",
        "device_ip": "192.168.1.200",
    }
