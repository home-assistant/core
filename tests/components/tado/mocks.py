"""Mocks for the tado component."""
import json
import os

from homeassistant.components.tado.tado_adapter import TadoZoneData

from tests.common import load_fixture


async def _mock_tado_climate_zone_from_fixture(hass, file):
    return TadoZoneData(await _load_json_fixture(hass, file), 1)


async def _load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("tado", path)
    )
    return json.loads(fixture)
