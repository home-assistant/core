"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pooldose.const import CONF_SERIALNUMBER, DOMAIN
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry


class TestPooldoseConfigFlow:
    """Test class for Seko Pooldose config flow."""

    @pytest.mark.asyncio
    async def test_form_shows_and_creates_entry(self, hass: HomeAssistant) -> None:
        """Test that the form is shown and entry is created on valid input."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(
                return_value={"APIVERSION_GATEWAY": "v1", "SERIAL_NUMBER": "SN123"}
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.CREATE_ENTRY
            assert result2["title"] == "PoolDose - S/N SN123"
            assert result2["data"] == {
                CONF_HOST: "1.2.3.4",
                CONF_SERIALNUMBER: "SN123",
            }

    @pytest.mark.asyncio
    async def test_form_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test that cannot_connect error is shown if host is unreachable."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(return_value=None),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_form_api_version_not_supported(self, hass: HomeAssistant) -> None:
        """Test that api_not_supported error is shown if API version is wrong."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(
                return_value={"APIVERSION_GATEWAY": "v0", "SERIAL_NUMBER": "SN123"}
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"] == {"base": "api_not_supported"}
            assert "api_version_is" in result2["description_placeholders"]
            assert "api_version_should" in result2["description_placeholders"]

    @pytest.mark.asyncio
    async def test_unique_id_abort(self, hass: HomeAssistant) -> None:
        """Test that flow aborts if unique_id is already configured."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(
                return_value={"APIVERSION_GATEWAY": "v1", "SERIAL_NUMBER": "SN123"}
            ),
        ):
            user_input = {CONF_HOST: "1.2.3.4"}
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

    @pytest.mark.asyncio
    async def test_options_flow_shows_and_saves(self, hass: HomeAssistant) -> None:
        """Test that the options flow form is shown and saves values."""
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"},
            options={CONF_SCAN_INTERVAL: 60, CONF_TIMEOUT: 10},
        )
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        user_input = {CONF_SCAN_INTERVAL: 120, CONF_TIMEOUT: 20}
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == user_input

    @pytest.mark.asyncio
    async def test_options_flow_invalid_input(self, hass: HomeAssistant) -> None:
        """Test that the options flow raises InvalidData for invalid input."""
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"},
            options={CONF_SCAN_INTERVAL: 60, CONF_TIMEOUT: 10},
        )
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        # Negative scan interval is invalid, should raise InvalidData
        user_input = {CONF_SCAN_INTERVAL: -1, CONF_TIMEOUT: 20}
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                result["flow_id"], user_input
            )

    @pytest.mark.asyncio
    async def test_options_flow_reconfigure(self, hass: HomeAssistant) -> None:
        """Test that the options flow can be used to reconfigure scan interval and timeout."""
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"},
            options={CONF_SCAN_INTERVAL: 60, CONF_TIMEOUT: 10},
        )
        mock_entry.add_to_hass(hass)

        # Start options flow
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        # Change values
        user_input = {CONF_SCAN_INTERVAL: 300, CONF_TIMEOUT: 15}
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == user_input
