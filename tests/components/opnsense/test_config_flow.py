"""Tests for the OPNsense config flow."""

from collections.abc import Iterable
from unittest.mock import AsyncMock, patch

from pyopnsense.exceptions import APIException

from homeassistant import data_entry_flow
from homeassistant.components.opnsense.const import CONF_TRACKER_INTERFACES, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, CONFIG_DATA_IMPORT

from tests.common import MockConfigEntry


async def test_import(
    hass: HomeAssistant, mock_diagnostics: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://router.lan/api"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user(
    hass: HomeAssistant, mock_diagnostics: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Use async_configure instead of async_init for form submission
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://router.lan/api"

    assert result.get("data") == CONFIG_DATA

    assert "result" in result
    config_entry: ConfigEntry | None = result.get("result")
    assert config_entry is not None

    subentries: Iterable[ConfigSubentryData] | None = result.get("subentries")
    assert subentries is not None
    assert subentries == ()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if component is already setup."""

    # Pretend we already set up a config entry.
    hass.config.components.add(DOMAIN)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_abort_import_if_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if component is already setup."""

    # Pretend we already set up a config entry.
    hass.config.components.add(DOMAIN)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_on_api_error(hass: HomeAssistant) -> None:
    """Test when we have errors connecting the router."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp",
        side_effect=APIException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("errors") == {"base": "cannot_connect"}

    # No error this time
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp"
    ):
        # Use async_configure instead of async_init for form submission
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_on_unknown_error(hass: HomeAssistant) -> None:
    """Test when we have unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp",
        side_effect=TypeError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "unknown"}

    # No error this time
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp"
    ):
        # Use async_configure instead of async_init for form submission
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_reconfigure_successful(
    hass: HomeAssistant, mock_diagnostics: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguration of an existing entry."""

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: ["LAN"]},
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TRACKER_INTERFACES] == ["LAN"]
