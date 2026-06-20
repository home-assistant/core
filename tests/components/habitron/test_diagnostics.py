"""Tests for the Habitron diagnostics support (habitron_client v2 model)."""

from datetime import timedelta
from unittest.mock import MagicMock

from habitron_client import Module, Router

from homeassistant.components.habitron.const import DOMAIN
from homeassistant.components.habitron.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_HOST,
    MOCK_HWTYPE,
    MOCK_NAME,
    MOCK_UID,
    MOCK_VERSION,
)

from tests.common import MockConfigEntry


def _module(uid: str = "MOD-1", name: str = "Living room") -> Module:
    return Module(
        uid=uid,
        addr=105,
        typ=b"\x01\x04",
        name=name,
        mod_type="Smart Controller Touch",
        sw_version="1.2.3",
    )


def _smhub(router: Router) -> MagicMock:
    smhub = MagicMock()
    smhub.uid = MOCK_UID
    smhub.smhub_name = MOCK_NAME
    smhub.smhub_type = MOCK_HWTYPE
    smhub.smhub_version = MOCK_VERSION
    smhub.host = MOCK_HOST
    smhub.addon_slug = ""
    smhub.online = True
    smhub.router = router
    smhub.coordinator = MagicMock(
        update_interval=timedelta(seconds=5),
        last_update_success=True,
        always_update=False,
    )
    return smhub


def _entry(hass: HomeAssistant, router: Router) -> MockConfigEntry:
    """A real config entry (for a valid entry_id) with a mock SmartHub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _smhub(router)
    return entry


async def test_config_entry_diagnostics(hass: HomeAssistant) -> None:
    """Config-entry diagnostics dump hub, router, coordinator and modules."""
    router = Router(uid="rt_1", id=100, name="Home", version="1.0", max_group=2)
    router.modules = [_module()]
    entry = _entry(hass, router)

    info = await async_get_config_entry_diagnostics(hass, entry)

    assert info["config_entry"]["unique_id"] == MOCK_UID
    assert info["config_entry"]["data"]["websock_token"] == "**REDACTED**"
    assert info["hub"]["uid"] == MOCK_UID
    assert info["hub"]["version"] == MOCK_VERSION
    assert info["hub"]["type"] == MOCK_HWTYPE
    assert info["router"]["module_count"] == 1
    assert info["coordinator"]["update_interval_seconds"] == 5
    assert info["coordinator"]["always_update"] is False
    assert info["modules"][0]["uid"] == "MOD-1"
    assert info["modules"][0]["type"] == "0104"


async def test_device_diagnostics_for_module(hass: HomeAssistant) -> None:
    """A device matching a module reports its module summary."""
    router = Router(uid="rt_1", id=100, name="Home")
    router.modules = [_module(uid="MOD-XYZ", name="Kitchen")]
    entry = _entry(hass, router)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "MOD-XYZ")},
        name="Kitchen Touch",
        model="Smart Controller Touch",
    )
    info = await async_get_device_diagnostics(hass, entry, device)
    assert info["device_identifier"] == "MOD-XYZ"
    assert info["target"]["kind"] == "module"
    assert info["target"]["summary"]["name"] == "Kitchen"


async def test_device_diagnostics_for_hub(hass: HomeAssistant) -> None:
    """A device matching the hub UID reports the hub summary."""
    entry = _entry(hass, Router(uid="rt_1", id=100, name="Home"))
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_UID)},
        name="SmartHub",
    )
    info = await async_get_device_diagnostics(hass, entry, device)
    assert info["target"]["kind"] == "hub"


async def test_device_diagnostics_for_router(hass: HomeAssistant) -> None:
    """A device whose UID matches the router reports the router summary."""
    router = Router(uid="rt_1", id=100, name="Home")
    entry = _entry(hass, router)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "rt_1")},
        name="Router",
    )
    info = await async_get_device_diagnostics(hass, entry, device)
    assert info["target"]["kind"] == "router"


async def test_device_diagnostics_unknown_identifier(hass: HomeAssistant) -> None:
    """A device whose UID is not in the router returns target=None."""
    entry = _entry(hass, Router(uid="rt_1", id=100, name="Home"))
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "ghost-uid")},
        name="Unknown",
    )
    info = await async_get_device_diagnostics(hass, entry, device)
    assert info["target"] is None
