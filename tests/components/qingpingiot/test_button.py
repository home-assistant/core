"""Test the qingpingiot button entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"


async def test_button_created_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test that CO2 calibration button is created for CGR1W model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    button_entities = [e for e in entities if e.unique_id == f"{MAC}_co2_calibration"]

    assert len(button_entities) == 1


async def test_button_press(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test pressing the CO2 calibration button."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.test_device_co2_manual_calibration")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.test_device_co2_manual_calibration"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify MQTT publish was called
    mqtt_mock.async_publish.assert_called()


async def test_no_button_for_model_without_capability(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test no button for CGS2 which lacks CO2_CALIBRATION capability."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233445566",
        data={
            CONF_MAC: "112233445566",
            CONF_MODEL: "cgs2",
            CONF_NAME: "Air Monitor",
        },
        title="Air Monitor",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    button_entities = [e for e in entities if "co2_calibration" in e.unique_id]
    assert len(button_entities) == 0
