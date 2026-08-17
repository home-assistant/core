"""Tests for the Dyson Infrared config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.dyson_infrared.const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_COMMAND_STEP_DELAY,
    DOMAIN,
    DysonDeviceType,
    DysonTemperatureUnit,
)
from homeassistant.const import CONF_TEMPERATURE_UNIT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("device_type", "expected_title"),
    [
        (DysonDeviceType.FAN, "Dyson Fan via My Living Room Emitter"),
        (
            DysonDeviceType.HEATER_COOLER,
            "Dyson Heater/Cooler via My Living Room Emitter",
        ),
    ],
)
async def test_form_and_create_entry(
    hass: HomeAssistant, device_type: DysonDeviceType, expected_title: str
) -> None:
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
            CONF_DEVICE_TYPE: device_type.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.my_living_room_emitter",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == expected_title
    assert result2["data"] == {
        **user_input,
        CONF_TEMPERATURE_UNIT: DysonTemperatureUnit.CELSIUS.value,
        CONF_COMMAND_STEP_DELAY: DEFAULT_COMMAND_STEP_DELAY,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert (
        result2["result"].unique_id
        == f"{device_type.value}_infrared.my_living_room_emitter"
    )


async def test_form_with_custom_command_step_delay(hass: HomeAssistant) -> None:
    """Test a custom command_step_delay value is stored on the entry."""
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
        ),
    ):
        mock_entry = AsyncMock()
        mock_entry.name = "My Living Room Emitter"
        mock_er.return_value.async_get.return_value = mock_entry

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.my_living_room_emitter",
            CONF_COMMAND_STEP_DELAY: 1.5,
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        **user_input,
        CONF_TEMPERATURE_UNIT: DysonTemperatureUnit.CELSIUS.value,
    }


async def test_form_defaults_temperature_unit_to_system_unit(
    hass: HomeAssistant,
) -> None:
    """Test the temperature unit defaults to the unit the system is configured for."""
    hass.config.units = US_CUSTOMARY_SYSTEM

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
        ),
    ):
        mock_entry = AsyncMock()
        mock_entry.name = "My Living Room Emitter"
        mock_er.return_value.async_get.return_value = mock_entry

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_TYPE: DysonDeviceType.HEATER_COOLER.value,
                CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.my_living_room_emitter",
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result2["data"][CONF_TEMPERATURE_UNIT] == DysonTemperatureUnit.FAHRENHEIT.value
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
        unique_id="fan_infrared.existing_emitter",
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
