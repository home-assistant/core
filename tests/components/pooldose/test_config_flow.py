"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, patch

from pooldose.request_handler import RequestHandler
import pytest

from homeassistant.components.pooldose.const import (
    CONF_INCLUDE_SENSITIVE_DATA,
    CONF_SERIALNUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_v1_api_handler():
    """Create a mock handler that always returns API version v1/."""
    handler = AsyncMock()
    handler.check_apiversion_supported.return_value = (
        "SUCCESS",
        {"api_version_is": "v1/", "api_version_should": "v1/"},
    )
    return handler


@pytest.fixture
def mock_v1_client():
    """Create a mock client with API version v1/."""
    return AsyncMock(
        device_info={
            "SERIAL_NUMBER": "SN123",
            "API_VERSION": "v1/",
            "DEVICE_NAME": "PoolDose Test",
        }
    )


class TestPooldoseConfigFlow:
    """Test class for Seko Pooldose config flow."""

    @pytest.mark.asyncio
    async def test_form_shows_and_creates_entry(
        self, hass: HomeAssistant, mock_v1_api_handler: RequestHandler
    ) -> None:
        """Test that the form is shown and entry is created on valid input."""

        with (
            patch(
                "homeassistant.components.pooldose.config_flow.RequestHandler.create",
                return_value=("SUCCESS", mock_v1_api_handler),
            ),
            patch(
                "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
                return_value=(
                    "SUCCESS",
                    AsyncMock(device_info={"SERIAL_NUMBER": "SN123"}),
                ),
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {}

            user_input = {
                CONF_HOST: "1.2.3.4",
                CONF_INCLUDE_SENSITIVE_DATA: False,
            }
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == FlowResultType.CREATE_ENTRY
            assert result2["data"][CONF_HOST] == "1.2.3.4"
            assert result2["data"][CONF_SERIALNUMBER] == "SN123"
            assert result2["data"][CONF_INCLUDE_SENSITIVE_DATA] is False

    @pytest.mark.asyncio
    async def test_form_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test that the form shows an error if the device is unreachable."""
        with patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=("HOST_UNREACHABLE", None),
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
    async def test_options_flow_shows_and_saves(self, hass: HomeAssistant) -> None:
        """Test that the options flow form is shown and saves values."""
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4", CONF_SERIALNUMBER: "SN123"},
            options={},
        )
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        user_input = {
            "scan_interval": 120,
            "timeout": 20,
            CONF_INCLUDE_SENSITIVE_DATA: True,
        }
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_INCLUDE_SENSITIVE_DATA] is True

    @pytest.mark.asyncio
    async def test_form_with_v1_api(
        self,
        hass: HomeAssistant,
        mock_v1_api_handler: AsyncMock,
        mock_v1_client: AsyncMock,
    ) -> None:
        """Test config flow with v1/ API version."""
        with (
            patch(
                "homeassistant.components.pooldose.config_flow.RequestHandler.create",
                return_value=("SUCCESS", mock_v1_api_handler),
            ),
            patch(
                "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
                return_value=("SUCCESS", mock_v1_client),
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )

            user_input = {
                CONF_HOST: "192.168.1.100",
                CONF_INCLUDE_SENSITIVE_DATA: True,
            }
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )

            assert result2["type"] == FlowResultType.CREATE_ENTRY
            # Überprüfe, dass die API-Version korrekt verwendet wurde
            mock_v1_api_handler.check_apiversion_supported.assert_called_once()
