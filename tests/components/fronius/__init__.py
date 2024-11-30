"""Tests for the Fronius integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import json
from typing import Any

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fronius.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_HOST = "http://fronius"
MOCK_UID = "123.4567890"


async def setup_fronius_integration(
    hass: HomeAssistant, is_logger: bool = True, unique_id: str = MOCK_UID
) -> ConfigEntry:
    """Create the Fronius integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="f1e2b9837e8adaed6fa682acaa216fd8",
        unique_id=unique_id,  # has to match mocked logger unique_id
        data={
            CONF_HOST: MOCK_HOST,
            "is_logger": is_logger,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _load_and_patch_fixture(
    override_data: dict[str, list[tuple[list[str], Any]]],
) -> Callable[[str, str | None], str]:
    """Return a fixture loader that patches values at nested keys for a given filename."""

    def load_and_patch(filename: str, integration: str):
        """Load a fixture and patch given values."""
        text = load_fixture(filename, integration)
        if filename not in override_data:
            return text

        _loaded = json.loads(text)
        for keys, value in override_data[filename]:
            _dic = _loaded
            for key in keys[:-1]:
                _dic = _dic[key]
            _dic[keys[-1]] = value
        return json.dumps(_loaded)

    return load_and_patch


def mock_responses(
    aioclient_mock: AiohttpClientMocker,
    host: str = MOCK_HOST,
    fixture_set: str = "symo",
    inverter_ids: list[str | int] | UndefinedType = UNDEFINED,
    night: bool = False,
    override_data: dict[str, list[tuple[list[str], Any]]]
    | None = None,  # {filename: [([list of nested keys], patch_value)]}
) -> None:
    """Mock responses for Fronius devices."""
    aioclient_mock.clear_requests()
    _night = "_night" if night else ""
    _load = _load_and_patch_fixture(override_data) if override_data else load_fixture

    aioclient_mock.get(
        f"{host}/solar_api/GetAPIVersion.cgi",
        text=_load(f"{fixture_set}/GetAPIVersion.json", "fronius"),
    )
    for inverter_id in [1] if inverter_ids is UNDEFINED else inverter_ids:
        aioclient_mock.get(
            f"{host}/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&"
            f"DeviceId={inverter_id}&DataCollection=CommonInverterData",
            text=_load(
                f"{fixture_set}/GetInverterRealtimeData_Device_{inverter_id}{_night}.json",
                "fronius",
            ),
        )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetInverterInfo.cgi",
        text=_load(f"{fixture_set}/GetInverterInfo{_night}.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetLoggerInfo.cgi",
        text=_load(f"{fixture_set}/GetLoggerInfo.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System",
        text=_load(f"{fixture_set}/GetMeterRealtimeData.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetPowerFlowRealtimeData.fcgi",
        text=_load(f"{fixture_set}/GetPowerFlowRealtimeData{_night}.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetStorageRealtimeData.cgi?Scope=System",
        text=_load(f"{fixture_set}/GetStorageRealtimeData.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetOhmPilotRealtimeData.cgi?Scope=System",
        text=_load(f"{fixture_set}/GetOhmPilotRealtimeData.json", "fronius"),
    )


async def enable_all_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry_id: str,
    time_till_next_update: timedelta,
) -> None:
    """Enable all entities for a config entry and fast forward time to receive data."""
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry_id)
    for entry in [
        entry
        for entry in entities
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    ]:
        registry.async_update_entity(entry.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    freezer.tick(time_till_next_update)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
