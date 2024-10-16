"""Test the Palazzetti config flow."""

from unittest.mock import patch

from pypalazzetti.exceptions import CommunicationError

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient.connect",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient.update_state",
            return_value=True,
        ) as mock_update_state,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient.mac",
            return_value="11:22:33:44:55:66",
        ) as mock_mac,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient.name",
            return_value="stove",
        ) as mock_name,
        patch(
            "homeassistant.components.palazzetti.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.1"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_connect.mock_calls) == 1
    assert len(mock_update_state.mock_calls) == 0
    assert len(mock_mac.mock_calls) > 0
    assert len(mock_name.mock_calls) > 0


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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_host"}
