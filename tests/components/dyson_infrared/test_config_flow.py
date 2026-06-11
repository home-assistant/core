"""Tests for the Dyson Infrared config flow."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from tests.common import MockConfigEntry

async def test_user_form_success(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test we get the form and create an entry when successful."""
    entity_registry.async_get_or_create(
        domain="infrared",
        platform="broadlink",
        unique_id="12345",
        suggested_object_id="broadlink_living_room",
        original_name="Broadlink Living Room",
    )

    # Allarghiamo il patch per coprire l'intero flusso di passaggi del form
    with patch(
        "homeassistant.components.infrared.async_get_emitters",
        new_callable=AsyncMock,
        return_value=["infrared.broadlink_living_room"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        with patch(
            "homeassistant.components.dyson_infrared.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry:
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
                    CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.broadlink_living_room",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dyson Fan via Broadlink Living Room"
    assert result2["data"] == {
        CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
        CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.broadlink_living_room",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_no_emitters(hass: HomeAssistant) -> None:
    """Test the flow aborts immediately if no infrared emitters are discovered."""
    with patch(
        "homeassistant.components.infrared.async_get_emitters",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


async def test_user_form_already_configured(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the flow aborts if the exact same device/emitter combo is already set up."""
    entity_registry.async_get_or_create(
        domain="infrared",
        platform="broadlink",
        unique_id="12345",
        suggested_object_id="broadlink_living_room",
    )

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="dyson_infrared_fan_infrared.broadlink_living_room",
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.broadlink_living_room",
        },
    )
    old_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.infrared.async_get_emitters",
        new_callable=AsyncMock,
        return_value=["infrared.broadlink_living_room"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
                CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.broadlink_living_room",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"