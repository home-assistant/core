"""Test the KEBA charging station config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_successful_setup(hass: HomeAssistant, mock_keba: MagicMock) -> None:
    """Test a successful config entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KC-P30"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == "12345678"


@pytest.mark.parametrize(
    ("setup_side_effect", "setup_return_value", "expected_error"),
    [
        pytest.param(None, False, "cannot_connect", id="no_response"),
        pytest.param(OSError("no route to host"), True, "cannot_connect", id="oserror"),
        pytest.param(Exception("unexpected error"), True, "unknown", id="unexpected"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    setup_side_effect: Exception | None,
    setup_return_value: bool,
    expected_error: str,
) -> None:
    """Test that connection problems in the user step show the matching error."""
    mock_keba.setup.side_effect = setup_side_effect
    mock_keba.setup.return_value = setup_return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # The flow must recover once the connection problem is fixed
    mock_keba.setup.side_effect = None
    mock_keba.setup.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_from_yaml(hass: HomeAssistant, mock_keba: MagicMock) -> None:
    """Test that a YAML config is silently imported as a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=ENTRY_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KC-P30"
    assert result["data"] == ENTRY_DATA


@pytest.mark.parametrize(
    ("setup_side_effect", "setup_return_value", "expected_reason"),
    [
        pytest.param(None, False, "cannot_connect", id="no_response"),
        pytest.param(OSError("no route to host"), True, "cannot_connect", id="oserror"),
        pytest.param(Exception("unexpected error"), True, "unknown", id="unexpected"),
    ],
)
async def test_import_errors(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    setup_side_effect: Exception | None,
    setup_return_value: bool,
    expected_reason: str,
) -> None:
    """Test that connection problems during import abort with the matching reason."""
    mock_keba.setup.side_effect = setup_side_effect
    mock_keba.setup.return_value = setup_return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=ENTRY_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("mock_keba", "mock_setup_entry")
async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a second setup is blocked because single_config_entry is true."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
