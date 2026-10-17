"""Real-``hass`` coverage for entity.py's platform-setup wiring.

``async_add_entities`` needs the ``entity_platform`` context var that only
exists while a platform's own ``async_setup_entry`` is actually running --
this can't be faked with a bare-instance/``SimpleNamespace`` coordinator,
unlike most of this test suite.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.components.truenas_ce.sensor import (
    TrueNASSensor,
    TrueNASUptimeSensor,
)
from homeassistant.components.truenas_ce.sensor_types import SENSOR_TYPES
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_sensor_types_func_values_all_have_a_dispatcher_entry() -> None:
    """Every SENSOR_TYPES description's ``func`` must resolve in sensor.py's dispatcher.

    A description whose ``func`` has no matching dispatcher entry raises
    ``KeyError`` inside ``entity._collect_new_entities`` and aborts that
    platform's entire setup (the historical ``TrueNASSnapshotTaskSensor``
    regression). This mirrors ``async_setup_entry``'s dispatcher literally so
    a future sensor description with an unmapped ``func`` fails here with a
    clear message instead of via an opaque platform-setup failure.
    """
    dispatcher = {
        "TrueNASSensor": TrueNASSensor,
        "TrueNASUptimeSensor": TrueNASUptimeSensor,
    }
    missing = {description.func for description in SENSOR_TYPES} - dispatcher.keys()
    assert not missing


# ---------------------------
#   async_add_entities (via a real platform-setup pass)
# ---------------------------
def _fake_api() -> SimpleNamespace:
    """A fake TrueNASAPI returning a minimal but valid system.info payload.

    system.info needs a real "hostname" or the coordinator's essential-
    hostname check aborts setup before these tests reach the entity-creation
    behaviour they actually exercise. Every other query returns None.
    """

    async def _query(method: str, *args: object, **kwargs: object) -> Any:
        return {"hostname": "truenas.local"} if method == "system.info" else None

    return SimpleNamespace(
        connected=MagicMock(return_value=True),
        connect=AsyncMock(return_value=True),
        close=AsyncMock(),
        query=AsyncMock(side_effect=_query),
        error="",
        scheme="ws",
    )


async def test_async_setup_entry_creates_entities_via_real_platform_setup(
    hass: HomeAssistant,
) -> None:
    """A real ``async_setup_entry`` run forwards to every platform.

    This exercises ``entity.async_add_entities``'s live wiring (service
    registration, dispatcher-connect, coordinator-identity check, entity
    creation) exactly as production does -- not reachable via a bare-instance
    coordinator since it needs the real ``entity_platform`` context var.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "test-key",
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=_fake_api(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids("sensor")
