from unittest.mock import patch

from homeassistant.components.tedee.const import (
    DOMAIN,
    CONF_HOME_ASSISTANT_ACCESS_TOKEN,
    CONF_LOCAL_ACCESS_TOKEN,
    NAME,
    CONF_UNLOCK_PULLS_LATCH,
    CONF_USE_CLOUD,
)

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FLOW_UNIQUE_ID = "112233445566778899"
ACCESS_TOKEN = "api_token"
LOCAL_ACCESS_TOKEN = "api_token"


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_CLOUD: True}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_cloud"


async def local_api_configure_error(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCAL_ACCESS_TOKEN: "token"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_local_config"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.42"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_local_config"}


async def test_show_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth form shows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
        unique_id=FLOW_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test that the reauth flow works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
        unique_id=FLOW_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    with patch(
        "homeassistant.components.tedee.async_setup_entry",
        return_value=True,
    ):
        reauth_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": entry.unique_id,
                "entry_id": entry.entry_id,
            },
            data={
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
            },
        )
        assert result["type"] == FlowResultType.ABORT
        await hass.async_block_till_done()
        assert result["reason"] == "reauth_successful"
