"""Test the touchline config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.touchline.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(name="setup")
def mock_controller_setup():
    """Mock controller setup."""
    with patch(
        "homeassistant.components.touchline.async_setup_entry", return_value=True
    ):
        yield


MOCK_DATA_IMPORT = {
    CONF_HOST: "http://1.1.1.1",
}
MOCK_NUMBER_OF_DEVICES = 1


async def test_form_successful(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        "touchline", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {} or result["errors"] is None

    with (
        patch(
            "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
            return_value={"type": "success", "data": "unique_id"},
        ),
        patch(
            "homeassistant.components.touchline.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_DATA_IMPORT
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "http://1.1.1.1"
    assert result2["data"] == MOCK_DATA_IMPORT


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(ConnectionRefusedError("unknown"), "cannot_connect")],
)
async def test_form_cannot_connect(
    hass: HomeAssistant, exception: ConnectionRefusedError, reason: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        "touchline", context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DATA_IMPORT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": reason}


async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""

    with patch(
        "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
        return_value={"type": "success", "data": "unique_id"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_DATA_IMPORT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_DATA_IMPORT
    assert len(mock_setup_entry.mock_calls) == MOCK_NUMBER_OF_DEVICES


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(ConnectionRefusedError("unknown"), "cannot_connect")],
)
async def test_import_flow_failure(
    hass: HomeAssistant, exception: ConnectionRefusedError, reason: str
) -> None:
    """Test handling errors while importing."""

    with patch(
        "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_DATA_IMPORT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
