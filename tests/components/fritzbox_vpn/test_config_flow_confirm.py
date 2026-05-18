"""Tests for SSDP confirm and user flow edge cases."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.fritzbox_vpn.config_flow import ConfigFlow
from custom_components.fritzbox_vpn.const import DOMAIN
from custom_components.fritzbox_vpn.flow_forms import InvalidAuth
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.fixtures import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME

MOCK_UDN = "uuid:2f402f80-da79-4e15-8e7b-4b6b6b6b6b6b"


@pytest.mark.asyncio
async def test_confirm_step_success(hass: HomeAssistant) -> None:
    """Confirm step creates entry after validation."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "confirm-test"
    flow._discovered_host = MOCK_HOST
    flow._discovered_unique_id = MOCK_HOST
    hass.config_entries.flow._progress[flow.flow_id] = flow

    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(return_value={"title": "Fritz!Box VPN"}),
    ):
        result = await flow.async_step_confirm(
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_confirm_step_invalid_host(hass: HomeAssistant) -> None:
    """Confirm step validates host before submit."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "confirm-test"
    flow._discovered_host = MOCK_HOST
    hass.config_entries.flow._progress[flow.flow_id] = flow

    result = await flow.async_step_confirm(
        {
            CONF_HOST: ".invalid",
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        }
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "invalid_host"


@pytest.mark.asyncio
async def test_confirm_shows_form(hass: HomeAssistant) -> None:
    """Confirm step shows form with discovered host placeholder."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow._discovered_host = MOCK_HOST
    flow._existing_config = None

    result = await flow.async_step_confirm()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


@pytest.mark.asyncio
async def test_confirm_step_validation_error(hass: HomeAssistant) -> None:
    """Confirm step shows form with base error when validation fails."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow._discovered_host = MOCK_HOST
    flow._discovered_unique_id = MOCK_HOST

    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=InvalidAuth),
    ):
        result = await flow.async_step_confirm(
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


def test_build_confirm_schema_from_existing() -> None:
    """Confirm schema prefills from existing Fritz integration config."""
    from custom_components.fritzbox_vpn.flow_forms import confirm_schema

    schema = confirm_schema(
        {CONF_HOST: MOCK_HOST, CONF_USERNAME: "u", CONF_PASSWORD: "p"},
        MOCK_HOST,
    )
    assert schema is not None
