"""Test the qingpingiot number entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.qingpingiot.const import (
    CONF_REPORT_INTERVAL,
    CONF_TEMPERATURE_OFFSET,
    CONF_HUMIDITY_OFFSET,
    DOMAIN,
)
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"


async def test_numbers_created_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test that expected number entities are created for CGR1W model."""
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

    entity_keys = {e.unique_id for e in entities}

    assert f"{MAC}_report_interval" in entity_keys
    assert f"{MAC}_temperature_offset" in entity_keys
    assert f"{MAC}_humidity_offset" in entity_keys


async def test_report_interval_default_value(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test report interval has correct default for CGR1W."""
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

    state = hass.states.get("number.test_device_interval_of_uploading")
    assert state is not None
    assert state.state == "60"


async def test_report_interval_set_value(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test setting report interval value."""
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

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.test_device_interval_of_uploading",
            "value": 30,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test_device_interval_of_uploading")
    assert state is not None
    assert state.state == "30"

    mqtt_mock.async_publish.assert_called()


async def test_offset_default_value(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test offset number entities default to 0."""
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

    state = hass.states.get("number.test_device_temp_compensation")
    assert state is not None
    assert state.state == "0"
