"""Test the Local File config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.local_file.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG


async def test_form(hass: HomeAssistant) -> None:
    """Test successful form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("os.access", return_value=True), patch(
        "homeassistant.components.local_file.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Local File", "file_path": "/test/file.jpg"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Local File"
    assert result2["data"] == {"name": "Local File", "file_path": "/test/file.jpg"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_path_invalid(hass: HomeAssistant) -> None:
    """Test retruning error if file path is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Local File", "file_path": "/test/file.jpg"},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"file_path": "not_valid"}


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""
    with patch("os.access", return_value=True), patch(
        "homeassistant.components.local_file.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Local File"
    assert result2["data"] == {"name": "Local File", "file_path": "/test/file.jpg"}
    assert len(mock_setup_entry.mock_calls) == 1
