"""Test the Steamist config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from . import (
    FORMATTED_MAC_ADDRESS,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _patch_discovery,
    _patch_status,
)

MODULE = "homeassistant.components.steamist"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status"
    ), patch(
        "homeassistant.components.steamist.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "127.0.0.1"
    assert result2["data"] == {
        "host": "127.0.0.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.steamist.config_flow.Steamist.async_get_status",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_discovery(hass: HomeAssistant):
    """Test setting up discovery."""
    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        # test we can try again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: FORMATTED_MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Master Bath"
    assert result3["data"] == {"host": "127.0.0.1", "name": "Master Bath"}
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_status(MOCK_ASYNC_GET_STATUS_INACTIVE):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"
