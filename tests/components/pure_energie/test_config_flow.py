"""Test the Pure Energie config flow."""
from unittest.mock import patch

from pure_energie import PureEnergieMeterError

from homeassistant.components.pure_energie.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch(
        "homeassistant.components.pure_energie.config_flow.PureEnergie.smartmeter"
    ) as mock_pure_energie, patch(
        "homeassistant.components.pure_energie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Name",
                CONF_HOST: "example.com",
            },
        )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "Name"
    assert result2.get("data") == {
        CONF_HOST: "example.com",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_pure_energie.mock_calls) == 1


async def test_api_error(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.pure_energie.PureEnergie.smartmeter",
        side_effect=PureEnergieMeterError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_NAME: "Name",
                CONF_HOST: "example.com",
            },
        )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("errors") == {"base": "cannot_connect"}
