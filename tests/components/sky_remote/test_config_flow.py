"""Test the Sky Remote config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from skyboxremote import LEGACY_PORT, SkyBoxConnectionError

from homeassistant.components.sky_remote.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SAMPLE_CONFIG


async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_remote_control
) -> None:
    """Test we can setup an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: SAMPLE_CONFIG[CONF_HOST]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == SAMPLE_CONFIG

    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_exists_abort(
    hass: HomeAssistant, mock_config_entry, mock_remote_control
) -> None:
    """Test we abort flow if device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: mock_config_entry.data[CONF_HOST]},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("mock_remote_control", [LEGACY_PORT], indirect=True)
async def test_user_flow_legacy_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remote_control,
) -> None:
    """Test we can setup an entry with a legacy port."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    async def mock_check_connectable():
        if mock_remote_control.call_args[0][1] == LEGACY_PORT:
            return True
        raise SkyBoxConnectionError("Wrong port")

    mock_remote_control._instance_mock.check_connectable = mock_check_connectable

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: SAMPLE_CONFIG[CONF_HOST]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**SAMPLE_CONFIG, CONF_PORT: LEGACY_PORT}

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_remote_control", [6], indirect=True)
async def test_user_flow_unconnectable(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remote_control,
) -> None:
    """Test we can setup an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    mock_remote_control._instance_mock.check_connectable = AsyncMock(
        side_effect=SkyBoxConnectionError("Example")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: SAMPLE_CONFIG[CONF_HOST]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    assert len(mock_setup_entry.mock_calls) == 0

    mock_remote_control._instance_mock.check_connectable = AsyncMock(True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: SAMPLE_CONFIG[CONF_HOST]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == SAMPLE_CONFIG

    assert len(mock_setup_entry.mock_calls) == 1
