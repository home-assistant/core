"""Test for the Fast.com config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.fastdotcom.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_form(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fastdotcom.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fast.com"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_single_instance_allowed(
    hass: HomeAssistant,
    source: str,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN)

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow."""
    with patch(
        "homeassistant.components.fastdotcom.__init__.SpeedtestData",
        return_value={"download": "50"},
    ), patch("homeassistant.components.fastdotcom.sensor.SpeedtestSensor"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Fast.com"
        assert result["data"] == {}
        assert result["options"] == {}
