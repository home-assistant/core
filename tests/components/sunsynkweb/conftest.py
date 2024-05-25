"""Common fixtures for the Sunsynk Inverter Web tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunsynkweb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def basicdata():
    """Return the normal start of coordinator minimal api required from the api."""
    return [
        {"msg": "Success", "data": {"access_token": "12345"}},
        {
            "msg": "Success",
            "data": {
                "infos": [
                    {"name": "plant1", "id": 1, "masterId": 1, "status": 0},
                    {"name": "plant2", "id": 2, "masterId": 1, "status": 0},
                ]
            },
        },
        # enrich inverters
        {"msg": "Success", "data": {"infos": [{"sn": 123}]}},
        {"msg": "Success", "data": {"infos": [{"sn": 345}]}},
        # inst data
        {
            "code": 200,
            "msg": "Success",
            "data": {
                "battPower": 1,
                "toBat": True,
                "soc": 2,
                "loadOrEpsPower": 3,
                "gridOrMeterPower": 4,
                "toGrid": True,
                "pvPower": 5,
            },
        },
        # PV total
        {
            "data": {
                "infos": [
                    {
                        "records": [
                            {"year": 2024, "value": 1},
                            {"year": 2023, "value": 2},
                        ]
                    }
                ]
            }
        },
        # total grid
        {"data": {"etotalTo": 2, "etotalFrom": 3}},
        # totalbattery
        {"data": {"etotalChg": 3, "etotalDischg": 4}},
        # total load
        {"data": {"totalUsed": 6}},
        # inst data inv2
        {
            "code": 200,
            "msg": "Success",
            "data": {
                "battPower": 1,
                "toBat": True,
                "soc": 2,
                "loadOrEpsPower": 3,
                "gridOrMeterPower": 4,
                "toGrid": True,
                "pvPower": 5,
            },
        },
        # PV total
        {
            "data": {
                "infos": [
                    {
                        "records": [
                            {"year": 2024, "value": 1},
                            {"year": 2023, "value": 2},
                        ]
                    }
                ]
            }
        },
        # total grid
        {"data": {"etotalTo": 2, "etotalFrom": 3}},
        # totalbattery
        {"data": {"etotalChg": 3, "etotalDischg": 4}},
        # total load
        {"data": {"totalUsed": 6}},
    ]
