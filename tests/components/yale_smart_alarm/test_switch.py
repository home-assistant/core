"""The test for the Yale smart living switch."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from yalesmartalarmclient import YaleSmartAlarmData

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_OFF
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SWITCH]],
)
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    load_config_entry: tuple[MockConfigEntry, Mock],
    get_data: YaleSmartAlarmData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Yale Smart Living autolock switch."""

    await snapshot_platform(
        hass, entity_registry, snapshot, load_config_entry[0].entry_id
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.device1_autolock",
        },
        blocking=True,
    )

    state = hass.states.get("switch.device1_autolock")
    assert state.state == STATE_OFF
