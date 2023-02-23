"""Test SPC config flow."""
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.spc.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    API_URL,
    CONF_CONFIG_FLOW,
    CONF_DATA,
    _create_mocked_spc,
    _patch_config_flow_spc,
)

from tests.common import MockConfigEntry


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    mocked_spc = await _create_mocked_spc()
    with _patch_config_flow_spc(mocked_spc), patch(
        "homeassistant.components.spc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id=API_URL,
    )

    entry.add_to_hass(hass)

    mocked_spc = await _create_mocked_spc()
    with _patch_config_flow_spc(mocked_spc), patch(
        "homeassistant.components.spc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_with_connection_failure(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    mocked_spc = await _create_mocked_spc(True)
    mocked_spc.async_load_parameters = AsyncMock(return_value=False)
    with _patch_config_flow_spc(mocked_spc), patch(
        "homeassistant.components.spc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "failed_to_connect"}


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    mocked_spc = await _create_mocked_spc()
    with _patch_config_flow_spc(mocked_spc), patch(
        "homeassistant.components.spc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=CONF_CONFIG_FLOW,
            context={"source": config_entries.SOURCE_IMPORT},
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == CONF_DATA


async def test_flow_import_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id=API_URL,
    )

    entry.add_to_hass(hass)

    mocked_spc = await _create_mocked_spc()
    with _patch_config_flow_spc(mocked_spc), patch(
        "homeassistant.components.spc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=CONF_CONFIG_FLOW,
            context={"source": config_entries.SOURCE_IMPORT},
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"
