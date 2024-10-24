"""Test the Palazzetti config flow."""

from unittest.mock import AsyncMock, patch

from pypalazzetti.exceptions import CommunicationError

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(hass: HomeAssistant, mock_palazzetti: AsyncMock) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient",
            mock_palazzetti,
        ) as mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.1"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_client.connect.mock_calls) > 0


async def test_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient.connect",
            side_effect=CommunicationError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "192.168.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
