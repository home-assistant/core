"""Test the PJLink config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

_DEFAULT_DATA = {CONF_HOST: "1.1.1.1", CONF_PORT: 4352, CONF_PASSWORD: "test-password"}


@pytest.fixture(autouse=True)
def mock_projector() -> Generator[AsyncMock]:
    """Mock the PJLink Projector in the config flow."""
    with patch(
        "homeassistant.components.pjlink.config_flow.Projector",
        autospec=True,
    ) as mock_projector:
        mock_instance = mock_projector.from_address.return_value
        mock_instance.get_name.return_value = "test name"
        yield mock_projector


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == _DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_projector: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_instance = mock_projector.from_address.return_value
    mock_instance.authenticate.side_effect = RuntimeError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_instance.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == _DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_projector: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_instance = mock_projector.from_address.return_value
    mock_instance.authenticate.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_instance.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == _DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1
