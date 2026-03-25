"""Test the PJLink config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.pjlink.const import CONF_ENCODING, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

_DEFAULT_DATA = {CONF_HOST: "1.1.1.1", CONF_PORT: 4352, CONF_PASSWORD: "test-password"}
_DEFAULT_DATA_WO_PORT = {CONF_HOST: "1.1.1.1", CONF_PASSWORD: "test-password"}
_DEFAULT_DATA_W_ENCODING = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 4352,
    CONF_PASSWORD: "test-password",
    CONF_ENCODING: "utf-8",
}


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


@pytest.mark.parametrize(
    ("side_effect", "error_str"),
    [
        (RuntimeError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_invalid_inputs(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: AsyncMock,
    side_effect: Exception,
    error_str: str,
) -> None:
    """Test we handle invalid inputs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_instance = mock_projector.from_address.return_value
    mock_instance.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_str}

    mock_instance.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == _DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "import_data",
    [_DEFAULT_DATA, _DEFAULT_DATA_WO_PORT, _DEFAULT_DATA_W_ENCODING],
)
async def test_import_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, import_data: dict[str, Any]
) -> None:
    """Test importing a YAML config creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=import_data
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == _DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_aborts_if_already_configured(hass: HomeAssistant) -> None:
    """Test importing a YAML config aborts if already configured."""
    # First import creates the entry
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=_DEFAULT_DATA
    )
    await hass.async_block_till_done()

    # Second import with same host should abort
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=_DEFAULT_DATA
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
