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

from homeassistant.components.truenas_ce.const import (
    CONF_MONITORED_GROUPS,
    DOMAIN,
    MONITOR_GROUP_SNAPSHOTS,
)
from homeassistant.components.truenas_ce.entity import format_unique_id
from homeassistant.components.truenas_ce.sensor_types import SENSOR_TYPES
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


# ---------------------------
#   async_add_entities (via a real platform-setup pass)
# ---------------------------
def _fake_api(extra_responses: dict[str, Any] | None = None) -> SimpleNamespace:
    """A fake TrueNASAPI returning a minimal but valid system.info payload.

    system.info needs a real "hostname" or the coordinator's essential-
    hostname check aborts setup before these tests reach the entity-creation
    behaviour they actually exercise. Every other query returns None unless
    ``extra_responses`` overrides it. ``client`` mirrors the same responses
    via ``.call()`` since ``TrueNASState`` calls it directly, bypassing
    ``TrueNASAPI.query()``.
    """
    responses = extra_responses or {}

    async def _query(method: str, *args: object, **kwargs: object) -> Any:
        if method in responses:
            return responses[method]
        return {"hostname": "truenas.local"} if method == "system.info" else None

    async def _client_call(method: str, params: object = None) -> Any:
        return await _query(method, params)

    return SimpleNamespace(
        connected=MagicMock(return_value=True),
        connect=AsyncMock(return_value=True),
        close=AsyncMock(),
        query=AsyncMock(side_effect=_query),
        error="",
        scheme="ws",
        client=SimpleNamespace(call=AsyncMock(side_effect=_client_call)),
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
        options={CONF_MONITORED_GROUPS: []},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=_fake_api(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids("sensor")


async def test_async_setup_entry_creates_snapshottask_sensor_via_dispatcher(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A description's ``func`` must have a matching dispatcher entry in its platform module.

    A missing one raises ``KeyError`` and aborts that platform's entire setup
    (the ``TrueNASSnapshotTaskSensor`` regression).
    """
    snapshottask_row = {"id": 1, "dataset": "tank/data", "state": {"state": "PENDING"}}
    fake_api = _fake_api(
        extra_responses={"pool.snapshottask.query": [snapshottask_row]}
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "test-key",
            CONF_VERIFY_SSL: False,
        },
        options={CONF_MONITORED_GROUPS: [MONITOR_GROUP_SNAPSHOTS]},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.truenas_ce.coordinator.TrueNASAPI",
        return_value=fake_api,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    snapshottask_description = next(
        d for d in SENSOR_TYPES if d.func == "TrueNASSnapshotTaskSensor"
    )
    # No CONF_SYSTEM_ID in this entry's data, so identity falls back to
    # entry_id (see entity.resolve_entry_identity) -- not the display name.
    unique_id = format_unique_id(entry.entry_id, snapshottask_description.key, 1)
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None
