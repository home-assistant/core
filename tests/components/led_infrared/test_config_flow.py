"""Test the LED Infrared config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LED light with 24-key remote via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test we abort when already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_requires_emitter(
    hass: HomeAssistant,
) -> None:
    """Test user flow requires an infrared emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfigure flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: None,
        },
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_INFRARED_ENTITY_ID] == EMITTER_ENTITY_ID

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_reconfigure_flow_requires_emitter(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow requires an infrared emitter."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_flow_reconfigure_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="0987654321",
        data={
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: None,
        },
    )
    config_entry.add_to_hass(hass)
    config_entry_2.add_to_hass(hass)
    result = await config_entry_2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow aborts when no infrared emitters exist."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"
