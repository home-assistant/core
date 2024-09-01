"""deCONZ select platform tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from pydeconz.models.sensor.air_purifier import AirPurifierFanMode
from pydeconz.models.sensor.presence import (
    PresenceConfigDeviceMode,
    PresenceConfigTriggerDistance,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType

from tests.common import snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_DATA = [
    (  # Presence Device Mode
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_id": "select.aqara_fp1_device_mode",
            "option": PresenceConfigDeviceMode.LEFT_AND_RIGHT.value,
            "request": "/sensors/0/config",
            "request_data": {"devicemode": "leftright"},
        },
    ),
    (  # Presence Sensitivity
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_id": "select.aqara_fp1_sensitivity",
            "option": "Medium",
            "request": "/sensors/0/config",
            "request_data": {"sensitivity": 2},
        },
    ),
    (  # Presence Trigger Distance
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_id": "select.aqara_fp1_trigger_distance",
            "option": PresenceConfigTriggerDistance.FAR.value,
            "request": "/sensors/0/config",
            "request_data": {"triggerdistance": "far"},
        },
    ),
    (  # Air Purifier Fan Mode
        {
            "config": {
                "filterlifetime": 259200,
                "ledindication": True,
                "locked": False,
                "mode": "speed_1",
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "de26d19d9e91b2db3ded6ee7ab6b6a4b",
            "lastannounced": None,
            "lastseen": "2024-08-07T18:27Z",
            "manufacturername": "IKEA of Sweden",
            "modelid": "STARKVIND Air purifier",
            "name": "IKEA Starkvind",
            "productid": "E2007",
            "state": {
                "deviceruntime": 73405,
                "filterruntime": 73405,
                "lastupdated": "2024-08-07T18:27:52.543",
                "replacefilter": False,
                "speed": 20,
            },
            "swversion": "1.1.001",
            "type": "ZHAAirPurifier",
            "uniqueid": "0c:43:14:ff:fe:6c:20:12-01-fc7d",
        },
        {
            "entity_id": "select.ikea_starkvind_fan_mode",
            "option": AirPurifierFanMode.AUTO.value,
            "request": "/sensors/0/config",
            "request_data": {"mode": "auto"},
        },
    ),
]


@pytest.mark.parametrize(("sensor_payload", "expected"), TEST_DATA)
async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful creation of button entities."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.SELECT]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Verify selecting option
    aioclient_mock = mock_put_request(expected["request"])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: expected["entity_id"],
            ATTR_OPTION: expected["option"],
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == expected["request_data"]
