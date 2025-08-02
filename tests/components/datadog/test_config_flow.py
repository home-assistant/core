"""Tests for the Datadog config flow."""

from unittest.mock import MagicMock, patch

from homeassistant.components import datadog
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from .common import MOCK_CONFIG, MOCK_DATA, MOCK_OPTIONS, MOCK_YAML_INVALID

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd"
    ) as mock_dogstatsd:
        mock_instance = MagicMock()
        mock_dogstatsd.return_value = mock_instance

        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["title"] == f"Datadog {MOCK_CONFIG['host']}"
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == MOCK_DATA
        assert result2["options"] == MOCK_OPTIONS


async def test_user_flow_retry_after_connection_fail(hass: HomeAssistant) -> None:
    """Test connection failure."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
        side_effect=OSError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN, context={"source": SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["data"] == MOCK_DATA
        assert result3["options"] == MOCK_OPTIONS


async def test_user_flow_abort_already_configured_service(
    hass: HomeAssistant,
) -> None:
    """Abort user-initiated config flow if the same host/port is already configured."""
    existing_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        datadog.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test that the options flow shows an error when connection fails."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
        side_effect=OSError("connection failed"),
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=MOCK_OPTIONS
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
    ):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=MOCK_OPTIONS
        )
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["data"] == MOCK_OPTIONS


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import triggers config flow and is accepted."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd"
        ) as mock_dogstatsd,
    ):
        mock_instance = MagicMock()
        mock_dogstatsd.return_value = mock_instance

        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_CONFIG,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_DATA
        assert result["options"] == MOCK_OPTIONS

        await hass.async_block_till_done()

        # Deprecation issue should be created
        issue = issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, "deprecated_yaml_datadog"
        )
        assert issue is not None
        assert issue.translation_key == "deprecated_yaml"
        assert issue.severity == ir.IssueSeverity.WARNING


async def test_import_connection_error(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import triggers connection error issue."""
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
        side_effect=OSError("connection refused"),
    ):
        result = await hass.config_entries.flow.async_init(
            datadog.DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_YAML_INVALID,
        )
        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"

        issue = issue_registry.async_get_issue(
            datadog.DOMAIN, "deprecated_yaml_import_connection_error"
        )
        assert issue is not None
        assert issue.translation_key == "deprecated_yaml_import_connection_error"
        assert issue.severity == ir.IssueSeverity.WARNING


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options after setup."""
    mock_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
    )
    mock_entry.add_to_hass(hass)

    new_options = {
        "prefix": "updated",
        "rate": 5,
    }

    # OSError Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
        side_effect=OSError,
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_options
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    # ValueError Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.options.async_init(mock_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_options
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    # Success Case
    with patch(
        "homeassistant.components.datadog.config_flow.DogStatsd"
    ) as mock_dogstatsd:
        mock_instance = MagicMock()
        mock_dogstatsd.return_value = mock_instance

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_options
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == new_options
        mock_instance.increment.assert_called_once_with("connection_test")


async def test_import_flow_abort_already_configured_service(
    hass: HomeAssistant,
) -> None:
    """Abort import if the same host/port is already configured."""
    existing_entry = MockConfigEntry(
        domain=datadog.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        datadog.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
