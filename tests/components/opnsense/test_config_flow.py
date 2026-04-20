"""Tests for the OPNsense config flow."""

from collections.abc import Iterable
from unittest.mock import AsyncMock, patch

from aiopnsense import OPNsenseConnectionError

from homeassistant import data_entry_flow
from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, CONFIG_DATA_IMPORT

from tests.common import MockConfigEntry


async def test_import(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://router.lan/api"


async def test_user(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Submit user step, should go to interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "interfaces"

    # Submit interfaces step (simulate user selecting all interfaces)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"tracker_interfaces": []},
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
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate",
        side_effect=OPNsenseConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "user"

        # Submit user step, should show error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("errors") == {"base": "cannot_connect"}

    # No error this time
    with (
        patch("homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces",
            return_value={"LAN": {"name": "LAN"}},
        ),
    ):
        # Submit user step, should go to interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "interfaces"

        # Submit interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"tracker_interfaces": []},
        )
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_on_unknown_error(hass: HomeAssistant) -> None:
    """Test when we have unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient.validate",
        side_effect=TypeError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("errors") == {"base": "unknown"}

    # No error this time
    with (
        patch("homeassistant.components.opnsense.config_flow.OPNsenseClient.validate"),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient.get_interfaces",
            return_value={"LAN": {"name": "LAN"}},
        ),
    ):
        # Submit user step, should go to interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_DATA,
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "interfaces"

        # Submit interfaces step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"tracker_interfaces": []},
        )
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
