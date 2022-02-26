"""Test the ebusd config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ebusd.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "ebusdpy.init",
    ) as mock_ebusdpy_init:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "circuit": "bai"},
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {}
    assert result2["last_step"] is True
    assert len(mock_ebusdpy_init.mock_calls) == 1

    with patch(
        "homeassistant.components.ebusd.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "HotWaterTemperature": True,
                "StorageTemperature": False,
            },
        )
    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "ebusd"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "circuit": "bai",
        "cache_ttl": 9000,
        "name": "ebusd",
        "port": 8888,
        "monitored_conditions": ["HotWaterTemperature"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "ebusdpy.init",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "circuit": "bai"},
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_entry_already_exists(hass: HomeAssistant) -> None:
    """Test the form aborts if it is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_id = "1.1.1.1:8888"
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=mock_id)
    mock_entry.add_to_hass(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "circuit": "bai"},
    )
    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_form_conditions_not_selected(hass: HomeAssistant) -> None:
    """Test we handle not selected conditions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "ebusdpy.init",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "circuit": "bai"},
        )
        await hass.async_block_till_done()

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {},
    )
    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "conditions_not_selected"}
