"""Tests for the Datadog config flow."""

from unittest.mock import MagicMock, patch

from homeassistant.components import datadog
from homeassistant.components.datadog.config_flow import DatadogConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import MOCK_CONFIG, MOCK_DATA, MOCK_OPTIONS

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["title"] == f"Datadog {MOCK_CONFIG['host']}"
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == MOCK_DATA
        assert result2["options"] == MOCK_OPTIONS


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=OSError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": "user"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["data"] == MOCK_DATA
        assert result3["options"] == MOCK_OPTIONS


async def test_options_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test that the options flow shows an error when connection fails."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
        unique_id="datadog_unique",
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=OSError("connection failed"),
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import triggers config flow and is accepted."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": "import"},
            data=MOCK_CONFIG,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_DATA
        assert result["options"] == MOCK_OPTIONS


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options after setup."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
        unique_id="datadog_unique",
    )
    mock_entry.add_to_hass(hass)

    new_config = {
        "host": "127.0.0.1",
        "port": 8126,
        "prefix": "updated",
        "rate": 5,
    }

    # OSError Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=OSError,
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_config
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    # ValueError Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_config
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    # Success Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd"
    ) as mock_dogstatsd:
        mock_instance = MagicMock()
        mock_dogstatsd.return_value = mock_instance

        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_config
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == new_config
        mock_instance.increment.assert_called_once_with("connection_test")


async def test_async_step_user_connection_fail(hass: HomeAssistant) -> None:
    """Test that the form shows an error when connection fails."""
    flow = DatadogConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=OSError("Connection failed"),
    ):
        result = await flow.async_step_user(
            {
                "host": "badhost",
                "port": 1234,
                "prefix": "prefix",
                "rate": 1,
            }
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow_abort_cannot_connect(hass: HomeAssistant) -> None:
    """Test import flow aborts if cannot connect to Datadog."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd.increment",
        side_effect=OSError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": "import"},
            data=MOCK_CONFIG,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
