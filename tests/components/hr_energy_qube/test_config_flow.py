"""Test the Qube Heat Pump config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.hr_energy_qube.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Qube heat pump"
    assert result["data"] == {CONF_HOST: "qube.local", CONF_PORT: 502}


@pytest.mark.parametrize(
    ("connect_side_effect", "connect_result", "version_result", "error"),
    [
        (None, False, "2.15", "cannot_connect"),
        (OSError, None, "2.15", "cannot_connect"),
        (None, True, None, "not_qube_device"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_setup_entry: AsyncMock,
    connect_side_effect: type[Exception] | None,
    connect_result: bool | None,
    version_result: str | None,
    error: str,
) -> None:
    """Test flow error handling with recovery."""
    mock_qube_client.connect = AsyncMock(
        side_effect=connect_side_effect, return_value=connect_result
    )
    mock_qube_client.async_get_software_version = AsyncMock(return_value=version_result)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Reset mocks for successful retry
    mock_qube_client.connect = AsyncMock(return_value=True)
    mock_qube_client.async_get_software_version = AsyncMock(return_value="2.15")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
