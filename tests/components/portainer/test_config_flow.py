"""Test the Portainer config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_create_success(
    hass: HomeAssistant, mock_portainer_client: AsyncMock
) -> None:
    """Test we handle creatinw with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ACCESS_TOKEN: "prt_xxx",
            CONF_URL: "https://127.0.0.1:9443",
            CONF_VERIFY_SSL: True,
        },
    )
    assert result["result"].unique_id == "https://127.0.0.1:9443"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_ACCESS_TOKEN) == "prt_xxx"
    assert result["data"].get(CONF_URL) == "https://127.0.0.1:9443"
    assert result["data"].get(CONF_VERIFY_SSL) is True


async def test_form_cannot_connect_and_recover(
    hass: HomeAssistant, mock_portainer_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    mock_portainer_client.get_status.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ACCESS_TOKEN: "prt_xxx",
            CONF_URL: "https://127.0.0.1:9443",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_portainer_client.get_status.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_TOKEN: "prt_xxx",
            CONF_URL: "https://127.0.0.1:9443",
            CONF_VERIFY_SSL: True,
        },
    )
    assert result2["result"].unique_id == "https://127.0.0.1:9443"
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2["data"].get(CONF_ACCESS_TOKEN) == "prt_xxx"
    assert result2["data"].get(CONF_URL) == "https://127.0.0.1:9443"
    assert result2["data"].get(CONF_VERIFY_SSL) is True
