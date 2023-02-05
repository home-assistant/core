"""Test the Sungrow Solar Energy config flow."""
from unittest.mock import patch

from pysungrow.definitions.devices.hybrid import sh10rt
from pysungrow.definitions.variables.device import OutputType

from homeassistant import config_entries
from homeassistant.components.sungrow.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.sungrow.config_flow.identify",
        return_value=("A1234567890", sh10rt, OutputType.THREE_PHASE_3P4L, []),
    ), patch(
        "homeassistant.components.sungrow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 502,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sungrow A1234567890"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 502,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_defaults(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.sungrow.config_flow.identify",
        return_value=("A1234567890", sh10rt, OutputType.THREE_PHASE_3P4L, []),
    ), patch(
        "homeassistant.components.sungrow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sungrow A1234567890"
    assert result2["data"] == {"host": "1.1.1.1", "port": 502}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sungrow.config_flow.identify",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
