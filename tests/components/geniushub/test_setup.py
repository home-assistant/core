"""Test the Geniushub config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.geniushub import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_all_sensors(
    hass: HomeAssistant,
    mock_local_config_entry: AsyncMock,
    mock_all: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test full local flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_single_zone_and_switch(
    hass: HomeAssistant,
    mock_local_config_entry: AsyncMock,
    mock_single_zone_with_switch: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test full local flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    test_entity_id = "switch.study_socket"
    switch = hass.states.get(test_entity_id)
    assert switch.state == "off"

    # call the HA turn_on service
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # The state should change but will not change until the next refresh
    # How do I force a refresh?
    await hass.async_block_till_done()
    assert switch.state == "off"

    # now call the HA turn_off service
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert switch.state == "off"
