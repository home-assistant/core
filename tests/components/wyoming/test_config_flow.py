"""Test the Wyoming config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from wyoming.info import AsrModel, AsrProgram, Attribution, Info

from homeassistant import config_entries
from homeassistant.components.wyoming.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

_TEST_ATTR = Attribution(name="Test", url="http://www.test.com")
_STT_INFO = Info(
    asr=[
        AsrProgram(
            name="Test ASR",
            installed=True,
            attribution=_TEST_ATTR,
            models=[
                AsrModel(
                    name="Test Model",
                    installed=True,
                    attribution=_TEST_ATTR,
                    languages=["en-US"],
                )
            ],
        )
    ]
)


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.wyoming.config_flow.load_wyoming_info",
        return_value=_STT_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Wyoming (Test ASR)"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 1234,
        "wyoming": _STT_INFO.to_dict(),
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wyoming.config_flow.load_wyoming_info",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"
