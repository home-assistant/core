"""Test the qingpingiot select entities."""

from unittest.mock import AsyncMock

from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"


async def test_temperature_unit_select_created_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test temperature unit select entity is created for CGR1W model."""
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

    select_entities = [e for e in entities if e.unique_id == f"{MAC}_temperature_unit"]

    assert len(select_entities) == 1


async def test_temperature_unit_select_options(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test temperature unit select has correct options."""
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

    state = hass.states.get("select.test_device_temperature_unit")
    assert state is not None
    assert state.state == "celsius"
    assert "celsius" in state.attributes["options"]
    assert "fahrenheit" in state.attributes["options"]


async def test_temperature_unit_select_change(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test changing temperature unit select value."""
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
        "select",
        "select_option",
        {
            "entity_id": "select.test_device_temperature_unit",
            "option": "fahrenheit",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.test_device_temperature_unit")
    assert state is not None
    assert state.state == "fahrenheit"

    mqtt_mock.async_publish.assert_called()


async def test_no_etvoc_select_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test no eTVOC select for CGR1W (no eTVOC capability)."""
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

    etvoc_entities = [e for e in entities if "etvoc_unit" in e.unique_id]
    assert len(etvoc_entities) == 0
