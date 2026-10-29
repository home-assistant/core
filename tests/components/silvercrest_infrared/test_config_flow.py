"""Test the SilverCrest Infrared config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.silvercrest_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SilverCrestIrDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    ("device_type", "device_name"),
    [
        (SilverCrestIrDeviceType.STVD45A1, "Tower fan STVD 45 A1"),
        (SilverCrestIrDeviceType.SSVS85A1, "Misting pedestal fan SSVS 85 A1"),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    device_type: SilverCrestIrDeviceType,
    device_name: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{device_name} via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: device_type,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
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
            CONF_DEVICE_TYPE: SilverCrestIrDeviceType.STVD45A1,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters_receivers(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters or receivers exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_requires_emitter(
    hass: HomeAssistant,
) -> None:
    """Test user flow requires an infrared emitter or receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_TYPE: SilverCrestIrDeviceType.STVD45A1},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: SilverCrestIrDeviceType.STVD45A1,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
