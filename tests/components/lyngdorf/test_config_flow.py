"""Configuration flow tests for the Lyngdorf integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import ssdp
from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_SERIAL = "aabbccddeeff"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_user_flow_shows_manual_form(hass: HomeAssistant) -> None:
    """Test user flow always shows manual IP form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test the manual configuration flow with MAC resolution."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with (
        patch(
            "homeassistant.components.lyngdorf.config_flow.getmac.get_mac_address",
            return_value=MOCK_MAC,
        ),
        patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == MOCK_SERIAL
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.data[CONF_SERIAL_NUMBER] == MOCK_SERIAL
    assert config_entry.title == "mp-60"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_manual_flow_no_mac(hass: HomeAssistant) -> None:
    """Test manual flow when MAC address cannot be resolved."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with (
        patch(
            "homeassistant.components.lyngdorf.config_flow.getmac.get_mac_address",
            return_value=None,
        ),
        patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == "mp-60:192.168.1.100"
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert CONF_SERIAL_NUMBER not in config_entry.data


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_manual_flow_already_configured(hass: HomeAssistant) -> None:
    """Test manual flow when device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={CONF_HOST: "192.168.1.50"},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with (
        patch(
            "homeassistant.components.lyngdorf.config_flow.getmac.get_mac_address",
            return_value=MOCK_MAC,
        ),
        patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (None, "unsupported_model"),
        (ConnectionError("Unable to connect"), "cannot_connect"),
        (TimeoutError("Connection timeout"), "timeout_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
    ids=["unsupported_model", "cannot_connect", "timeout", "unknown"],
)
async def test_manual_flow_errors(
    hass: HomeAssistant,
    side_effect: Exception | None,
    expected_error: str,
) -> None:
    """Test manual flow error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_kwargs: dict = {}
    if side_effect is not None:
        mock_kwargs["side_effect"] = side_effect
    else:
        mock_kwargs["return_value"] = None

    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        **mock_kwargs,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
