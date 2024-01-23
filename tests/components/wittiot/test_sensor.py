"""Test sensor of WittIOT integration."""
import json
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wittiot.const import CONNECTION_TYPE, DEVICE_NAME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="GW2000B-WIFICB44",
        data={
            DEVICE_NAME: "GW2000B-WIFICB44",
            CONF_HOST: "1.1.1.1",
            CONNECTION_TYPE: "Local",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "wittiot.API.request_loc_allinfo",
        return_value=json.loads(load_fixture("wittiot/device_data.json")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 78
    for entry in entity_registry.entities.values():
        state = hass.states.get(entry.entity_id)
        assert state
        assert state == snapshot(name=f"{entry.entity_id}-state")
