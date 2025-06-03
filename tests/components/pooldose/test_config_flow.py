"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pooldose.const import CONF_SERIALNUMBER, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class TestPooldoseConfigFlow:
    """Test class for Seko Pooldose config flow."""

    @pytest.mark.asyncio
    async def test_form_shows_and_creates_entry(self, hass: HomeAssistant) -> None:
        """Test that the form is shown and entry is created on valid input."""
        with patch(
            "homeassistant.components.pooldose.config_flow.PooldoseConfigFlow._async_check_host_reachable",
            new=AsyncMock(return_value=True),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.CREATE_ENTRY
            assert result2["title"] == "Pooldose - S/N SN123"
            assert result2["data"] == user_input

    @pytest.mark.asyncio
    async def test_form_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test that cannot_connect error is shown if host is unreachable."""
        with patch(
            "homeassistant.components.pooldose.config_flow.PooldoseConfigFlow._async_check_host_reachable",
            new=AsyncMock(return_value=False),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_unique_id_abort(self, hass: HomeAssistant) -> None:
        """Test that flow aborts if unique_id is already configured."""
        with patch(
            "homeassistant.components.pooldose.config_flow.PooldoseConfigFlow._async_check_host_reachable",
            new=AsyncMock(return_value=True),
        ):
            user_input = {CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"}
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )

            result2 = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.ABORT
            assert result2["reason"] == "already_configured"
