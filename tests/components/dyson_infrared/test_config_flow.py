"""Tests for the Dyson Infrared config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_and_create_entry(hass: HomeAssistant) -> None:
    """Test that the user config flow shows the form and creates an entry."""
    with (
        patch(
            "homeassistant.components.dyson_infrared.config_flow.infrared.async_get_emitters",
            return_value=["infrared.my_living_room_emitter"],
        ),
        patch(
            "homeassistant.components.dyson_infrared.config_flow.er.async_get",
        ) as mock_er,
        patch(
            "homeassistant.components.dyson_infrared.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_entry = AsyncMock()
        mock_entry.name = "My Living Room Emitter"
        mock_er.return_value.async_get.return_value = mock_entry

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None

        user_input = {
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.my_living_room_emitter",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dyson Fan via My Living Room Emitter"
    assert result2["data"] == user_input
    assert len(mock_setup_entry.mock_calls) == 1
    assert (
        result2["result"].unique_id
        == "dyson_infrared_fan_infrared.my_living_room_emitter"
    )


async def test_abort_no_emitters(hass: HomeAssistant) -> None:
    """Test abort when no infrared emitters are available."""
    with patch(
        "homeassistant.components.dyson_infrared.config_flow.infrared.async_get_emitters",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test abort when the infrared emitter is already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.existing_emitter",
        },
        unique_id="dyson_infrared_fan_infrared.existing_emitter",
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dyson_infrared.config_flow.infrared.async_get_emitters",
        return_value=["infrared.existing_emitter"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.existing_emitter",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
