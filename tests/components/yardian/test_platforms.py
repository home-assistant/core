"""Validate Yardian binary sensor behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pyyardian.async_client import YardianDeviceState

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


class FakeYardianClient:
    """Fake AsyncYardianClient returning deterministic data."""

    def __init__(self, *_: object, **__: object) -> None:
        """Create async mocks used by the integration."""
        self.stop_irrigation = AsyncMock()
        self.start_irrigation = AsyncMock()

    async def fetch_device_state(self) -> YardianDeviceState:
        """Return fake YardianDeviceState with three zones and one active."""
        zones = [["Zone 1", 1], ["Zone 2", 0], ["Zone 3", 1]]
        active_zones = {0}
        return YardianDeviceState(zones=zones, active_zones=active_zones)

    async def fetch_oper_info(self) -> dict[str, object]:
        """Return operation info relevant for binary sensors."""
        return {
            "iStandby": 0,
            "fFreezePrevent": 1,
        }


def _mock_entry() -> MockConfigEntry:
    """Return a configured Yardian config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "access_token": "abc",
            "name": "Yardian",
            "yid": "yid123",
            "model": "PRO1902",
            "serialNumber": "SN1",
        },
        title="Yardian Smart Sprinkler",
        unique_id="yid123",
    )


@pytest.mark.asyncio
async def test_binary_sensors_setup(hass: HomeAssistant) -> None:
    """Binary sensors are created and device info tracked."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    entity_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, "yid123_watering-running"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "on"
    assert state.attributes.get("device_class") == "running"

    # Ensure no stop button is created by default
    assert ent_reg.async_get_entity_id("button", DOMAIN, "yid123-stop") is None

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "yid123")})
    assert device is not None
    assert device.serial_number == "SN1"


@pytest.mark.asyncio
async def test_binary_sensor_state_updates(hass: HomeAssistant) -> None:
    """Standby and freeze prevent sensors reflect operation info."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    standby_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "yid123_standby")
    freeze_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, "yid123_freeze-prevent"
    )
    assert standby_id and freeze_id

    standby_state = hass.states.get(standby_id)
    freeze_state = hass.states.get(freeze_id)

    assert standby_state is not None and standby_state.state == "off"
    assert freeze_state is not None and freeze_state.state == "on"

    standby_entry = ent_reg.async_get(standby_id)
    freeze_entry = ent_reg.async_get(freeze_id)
    assert (
        standby_entry is not None
        and standby_entry.entity_category is EntityCategory.DIAGNOSTIC
    )
    assert (
        freeze_entry is not None
        and freeze_entry.entity_category is EntityCategory.DIAGNOSTIC
    )


@pytest.mark.asyncio
async def test_zone_enabled_sensor_enabling(hass: HomeAssistant) -> None:
    """Per-zone enabled binary sensors can be enabled and reflect state."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    zone_entity_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, "yid123_zone-enabled-0"
    )
    assert zone_entity_id is not None

    # Registry entry should be disabled by default
    reg_entry = ent_reg.async_get(zone_entity_id)
    assert reg_entry is not None
    assert reg_entry.disabled
    assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    # Enable and reload to surface state
    ent_reg.async_update_entity(zone_entity_id, disabled_by=None)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(zone_entity_id)
    assert state is not None and state.state == "on"


@pytest.mark.asyncio
async def test_zone_enabled_sensors_disabled_by_default(hass: HomeAssistant) -> None:
    """All per-zone binary sensors remain disabled by default."""

    entry = _mock_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient",
            return_value=FakeYardianClient(),
        ),
        patch(
            "homeassistant.requirements.RequirementsManager.async_process_requirements",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    for idx in range(3):
        entity_id = ent_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, f"yid123_zone-enabled-{idx}"
        )
        assert entity_id is not None
        reg_entry = ent_reg.async_get(entity_id)
        assert reg_entry is not None
        assert reg_entry.disabled
        assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert reg_entry.entity_category is EntityCategory.DIAGNOSTIC
