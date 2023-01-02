"""Test the FiveM config flow."""
from unittest.mock import patch

from fivem import FiveMServerOfflineError

from homeassistant import config_entries
from homeassistant.components.fivem.config_flow import DEFAULT_PORT
from homeassistant.components.fivem.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_HOST: "fivem.dummyserver.com",
    CONF_PORT: DEFAULT_PORT,
}


def _mock_fivem_info_success():
    return {
        "resources": [
            "fivem",
            "monitor",
        ],
        "server": "FXServer-dummy v0.0.0.DUMMY linux",
        "vars": {
            "gamename": "gta5",
        },
        "version": 123456789,
    }


def _mock_fivem_info_invalid():
    return {
        "plugins": [
            "sample",
        ],
        "data": {
            "gamename": "gta5",
        },
    }


def _mock_fivem_info_invalid_game_name():
    info = _mock_fivem_info_success()
    info["vars"]["gamename"] = "redm"

    return info


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "fivem.fivem.FiveM.get_info_raw",
        return_value=_mock_fivem_info_success(),
    ), patch(
        "homeassistant.components.fivem.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == USER_INPUT[CONF_HOST]
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "fivem.fivem.FiveM.get_info_raw",
        side_effect=FiveMServerOfflineError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "fivem.fivem.FiveM.get_info_raw",
        return_value=_mock_fivem_info_invalid(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_game_name(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "fivem.fivem.FiveM.get_info_raw",
        return_value=_mock_fivem_info_invalid_game_name(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_game_name"}
