"""Shared helpers for WyBot entity-platform tests.

Builds a real ``WyBotCoordinator`` (its constructor is side-effect free: it
creates MQTT/BLE client objects but does not connect) populated with real
``Group`` models so the entity platforms can be exercised end-to-end.
"""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from wybot.dp_models import DP
from wybot.models import Group

from homeassistant.components.wybot.const import DOMAIN
from homeassistant.components.wybot.coordinator import WyBotCoordinator
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, MockEntityPlatform

GROUP_DATA = {
    "device": {
        "deviceId": "dev1",
        "deviceName": "Robot",
        "deviceType": "S2 Pro",
        "bleName": "CCBA97932A96",
        "autoUpdate": "1",
        "version": {"Firmware": "1.0"},
    },
    "docker": {
        "dockerId": "dock1",
        "dockerType": "DS20",
        "bleName": "3C8427565A1A",
        "deviceStatus": "online",
        "dockerStatus": "active",
        "schedule": None,
        "version": {"Firmware": "2.0"},
    },
    "vision": {
        "visionId": "v1",
        "privacy": False,
        "log": None,
        "video": None,
        "picture": None,
        "policy": True,
    },
    "name": "My Pool",
    "id": "grp1",
    "autoUpdate": "1",
}


def dp(cls, **kwargs):
    """Wrap a raw DP into the given typed DP class."""
    return cls(DP(**kwargs))


def make_group(device_dps=None, docker_dps=None, with_docker=True, name="My Pool"):
    """Build a real ``Group`` with typed DP instances attached."""
    data = deepcopy(GROUP_DATA)
    data["name"] = name
    if not with_docker:
        data["docker"] = None
    group = Group(**data)
    group.device.dps = device_dps or {}
    if group.docker:
        group.docker.dps = docker_dps or {}
    return group


def make_coordinator(hass: HomeAssistant, data):
    """Build a real coordinator populated with the given ``data`` mapping."""
    entry_data = {CONF_USERNAME: "u", CONF_PASSWORD: "p"}
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)
    coord = WyBotCoordinator(hass, MagicMock(), entry)
    coord.data = data
    coord._connection_available = True
    # Avoid scheduling a real refresh timer when entities register as listeners
    # (keeps the test harness free of lingering timers).
    coord.update_interval = None
    return coord, entry


async def add_entity(hass: HomeAssistant, entity, domain="sensor"):
    """Add an entity to a real (mock) entity platform.

    This gives the entity a platform, hass, and entity_id so
    ``async_write_ha_state`` works exactly as it would in production.
    """
    platform = MockEntityPlatform(hass, domain=domain, platform_name=DOMAIN)
    await platform.async_add_entities([entity])
    return entity


async def setup_integration(hass: HomeAssistant, data):
    """Fully set up the WyBot integration with mocked clients and given data.

    Returns the config entry; its ``runtime_data`` is the real coordinator
    (pre-populated with ``data``). Entities are created by the real platform
    setup, so callers assert against the entity registry.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    entry.add_to_hass(hass)

    async def _fake_update(self):
        self.data = data
        self._connection_available = True
        return data

    with (
        patch("homeassistant.components.wybot.WyBotHTTPClient") as http_cls,
        patch.object(WyBotCoordinator, "_async_update_data", autospec=True) as update,
    ):
        http_cls.return_value.authenticate = AsyncMock()
        update.side_effect = _fake_update
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
