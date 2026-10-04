"""Test the Netis Router sensor platform.

Verifies sensor entity creation and state values by reading from the
integration's mocked coordinator snapshot.
"""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"


def _entity_id(hass: HomeAssistant, key: str) -> str:
    """Resolve a sensor entity_id from its unique key."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ENTRY_ID}-{key}"
    )
    assert entity_id is not None, f"sensor {key} not registered"
    return entity_id


async def test_uptime(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "uptime")).state == "3600"


async def test_wan_download_speed(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wan_download_speed")).state == "51200"


async def test_wan_upload_speed(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wan_upload_speed")).state == "102400"


async def test_wan_download_total(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wan_download_total")).state == "1024000"


async def test_wan_upload_total(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wan_upload_total")).state == "2048000"


async def test_online_devices(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "online_devices")).state == "2"


async def test_lte_rsrp(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_rsrp")).state == "-95.5"


async def test_lte_rsrq(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_rsrq")).state == "-12.3"


async def test_lte_rssi(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_rssi")).state == "28.0"


async def test_lte_mode(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_mode")).state == "LTE"


async def test_lte_isp(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_isp")).state == "CHN-CT"


async def test_lte_ip(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_ip")).state == "10.99.249.101"


async def test_firmware(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "firmware")).state == "4.0.260701.100631"


async def test_imei(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "imei")).state == "868245050137472"
