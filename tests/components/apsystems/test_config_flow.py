"""Test the APsystems Local API config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.apsystems.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_create_success(
    hass: HomeAssistant, mock_setup_entry, mock_apsystems
) -> None:
    """Test we handle creatinw with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"


async def test_form_cannot_connect_and_recover(
    hass: HomeAssistant, mock_apsystems: AsyncMock, mock_setup_entry
) -> None:
    """Test we handle cannot connect error."""

    mock_apsystems.return_value.get_device_info.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_apsystems.return_value.get_device_info.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result2["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"


async def test_form_unique_id_already_configured(
    hass: HomeAssistant, mock_setup_entry, mock_apsystems
) -> None:
    """Test we handle cannot connect error."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_IP_ADDRESS: "127.0.0.2"}, unique_id="MY_SERIAL_NUMBER"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )
    assert result["reason"] == "already_configured"
    assert result.get("type") is FlowResultType.ABORT
