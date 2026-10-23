"""Tests for the NAD Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nad_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    NADDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("device_type", "expected_title"),
    [
        (NADDeviceType.RECEIVER, "NAD receiver"),
        (NADDeviceType.AMPLIFIER, "NAD amplifier"),
        (NADDeviceType.CD_PLAYER, "NAD CD player"),
        (NADDeviceType.CASSETTE_DECK, "NAD cassette deck"),
    ],
)
async def test_user_flow_success(
    hass: HomeAssistant,
    device_type: NADDeviceType,
    expected_title: str,
) -> None:
    """Test successful user config flow for each device type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [
        "receiver",
        "amplifier",
        "cd_player",
        "cassette_deck",
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": device_type.value}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == device_type.value

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_DEVICE_TYPE: device_type,
        CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
    }
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when the device type already uses the emitter."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": NADDeviceType.RECEIVER.value}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_other_device_type_same_emitter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test another device type can share an emitter that is already in use."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": NADDeviceType.AMPLIFIER.value}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
