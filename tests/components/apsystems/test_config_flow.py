"""Test the APsystems Local API config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.apsystems.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_cannot_connect_and_recover(
    hass: HomeAssistant, mock_apsystems_timeout: AsyncMock, mock_setup_entry
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.apsystems.config_flow.APsystemsEZ1M",
        return_value=AsyncMock(),
    ) as mock_api:
        ret_data = MagicMock()
        ret_data.deviceId = "MY_SERIAL_NUMBER"
        mock_api.return_value.get_device_info = AsyncMock(return_value=ret_data)
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
    hass: HomeAssistant, mock_setup_entry, mock_apsystems_with_serial_id
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_IP_ADDRESS) == "127.0.0.2"
    assert result["result"].unique_id == "MY_SERIAL_NUMBER"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )
    assert result2["reason"] == "already_configured"
    assert result2.get("type") is FlowResultType.ABORT


async def test_form_create_success(
    hass: HomeAssistant, mock_setup_entry, mock_apsystems_with_serial_id
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
