"""Tests for the ZHA Infrared config flow."""

from unittest.mock import patch

from homeassistant.components.zha_infrared import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_aborts_without_zha(hass: HomeAssistant) -> None:
    """Abort when ZHA is not configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_zha"


async def test_user_flow_aborts_without_supported_devices(hass: HomeAssistant) -> None:
    """Abort when no TS1201-like devices are discovered."""
    MockConfigEntry(domain="zha", data={}).add_to_hass(hass)

    with patch(
        "homeassistant.components.zha_infrared.config_flow.get_supported_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"


async def test_user_flow_create_entry(hass: HomeAssistant) -> None:
    """Create a single integration entry when supported devices exist."""
    MockConfigEntry(domain="zha", data={}).add_to_hass(hass)

    with patch(
        "homeassistant.components.zha_infrared.config_flow.get_supported_devices",
        return_value=[object()],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZHA Infrared"
    assert result["data"] == {}


async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """Abort when the integration is already configured."""
    MockConfigEntry(domain="zha", data={}).add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.zha_infrared.config_flow.get_supported_devices",
        return_value=[object()],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
