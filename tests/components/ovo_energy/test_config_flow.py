"""Test the OVO Energy config flow."""
import aiohttp

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ovo_energy.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.async_mock import patch

FIXTURE_USER_INPUT = {CONF_USERNAME: "example@example.com", CONF_PASSWORD: "something"}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "authorization_error"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "connection_error"}


async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result2["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
