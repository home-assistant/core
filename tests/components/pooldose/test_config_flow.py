"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.pooldose.config_flow import (
    APIVERSION,
    validate_api_version,
)
from homeassistant.components.pooldose.const import (
    CONF_SERIALNUMBER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry


def get_default(schema: vol.Schema, key: str):
    """Extract the default value for a key from a voluptuous schema."""
    for field in schema.schema:
        if hasattr(field, "schema") and field.schema == key:
            default = getattr(field, "default", None)
            # if default is a Callable (lambda exp)
            if callable(default):
                return default()
            return default
    return None


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
            assert result2["data"][CONF_HOST] == "1.2.3.4"
            assert result2["data"][CONF_SERIALNUMBER] == "SN123"

    @pytest.mark.asyncio
    async def test_form_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test that the form shows an error if the device is unreachable."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(return_value=None),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_form_api_version_not_supported(self, hass: HomeAssistant) -> None:
        """Test that the form shows an error if the API version is not supported."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(
                return_value={"APIVERSION_GATEWAY": "old", "SERIAL_NUMBER": "SN123"}
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"]["base"] == "api_not_supported"
            assert "api_version_is" in result2["description_placeholders"]

    @pytest.mark.asyncio
    async def test_unique_id_abort(self, hass: HomeAssistant) -> None:
        """Test that the flow aborts if the unique_id is already configured."""
        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            new=AsyncMock(
                return_value={"APIVERSION_GATEWAY": "v1", "SERIAL_NUMBER": "SN123"}
            ),
        ):
            # First entry
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            user_input = {CONF_HOST: "1.2.3.4"}
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            # Second attempt with same serial
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

    @pytest.mark.asyncio
    async def test_options_flow_defaults(self, hass: HomeAssistant) -> None:
        """Test that the options flow uses default values if options are missing."""
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            options={},  # No options set
        )
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        scan_interval_default = get_default(result["data_schema"], CONF_SCAN_INTERVAL)
        timeout_default = get_default(result["data_schema"], CONF_TIMEOUT)
        assert scan_interval_default == DEFAULT_SCAN_INTERVAL
        assert timeout_default == DEFAULT_TIMEOUT

    def test_validate_api_version(self):
        """Test the validate_api_version helper."""

        # Supported version
        valid, placeholders = validate_api_version(APIVERSION)
        assert valid is True
        assert placeholders is None

        # Unsupported version
        valid, placeholders = validate_api_version("old")
        assert valid is False
        assert placeholders["api_version_is"] == "old"
        assert placeholders["api_version_should"] == APIVERSION

    @pytest.mark.asyncio
    async def test_config_flow_unknown_error(self, hass: HomeAssistant) -> None:
        """Test that the config flow handles unknown exceptions gracefully."""

        async def raise_exc(*args, **kwargs):
            raise Exception  # noqa: TRY002

        with patch(
            "homeassistant.components.pooldose.config_flow.get_device_info",
            side_effect=raise_exc,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            user_input = {CONF_HOST: "1.2.3.4"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == "form"
            assert result2["errors"]["base"] == "unknown"
