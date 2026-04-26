"""Test the Honeywell String Lights config flow."""

from __future__ import annotations

from homeassistant.components.honeywell_string_lights.const import (
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TRANSMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity


async def test_user_flow(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the user config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )

    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Honeywell String Lights"
    assert result["data"] == {CONF_TRANSMITTER: entity_entry.id}
    assert result["result"].unique_id == entity_entry.id


async def test_unique_id_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the same transmitter is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_transmitters(hass: HomeAssistant) -> None:
    """Test the flow aborts when no RF transmitters are registered at all."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_no_compatible_transmitters(hass: HomeAssistant) -> None:
    """Test aborting when transmitters exist but none support 433.92 MHz OOK."""
    assert await async_setup_component(hass, RF_DOMAIN, {})
    await hass.async_block_till_done()
    incompatible = MockRadioFrequencyEntity(
        "incompatible", frequency_ranges=[(868_000_000, 869_000_000)]
    )
    await hass.data[DATA_COMPONENT].async_add_entities([incompatible])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_compatible_transmitters"
