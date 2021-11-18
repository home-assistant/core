"""Tests for the Tuya base class."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from tuya_iot import TuyaDevice

from homeassistant.components.tuya.climate import (
    CLIMATE_DESCRIPTIONS,
    TuyaClimateEntity,
)
from homeassistant.components.tuya.const import DPCode


def create_tuya_device(
    id: str,
    category: str,
    status: dict[str, Any],
    status_range: dict[str, SimpleNamespace],
) -> TuyaDevice:
    """Test helper method to create a tuya device."""
    device = TuyaDevice()
    device.id = id
    device.category = category
    device.name = id + "_name"
    device.status = status
    device.status_range = status_range
    return device


DEVICE_FOLLOWING_SPECS = create_tuya_device(
    "int_device_following_specs",
    "kt",
    {
        DPCode.SWITCH + "": False,
        DPCode.TEMP_SET + "": 20,
        DPCode.TEMP_CURRENT + "": 20,
        DPCode.C_F + "": "C",
    },
    {
        DPCode.SWITCH
        + "": SimpleNamespace(
            **{
                "code": DPCode.SWITCH + "",
                "type": "Boolean",
                "values": "{}",
            }
        ),
        DPCode.TEMP_SET
        + "": SimpleNamespace(
            **{
                "code": DPCode.TEMP_SET + "",
                "type": "Integer",
                "values": '{"unit":"C","min":16,"max":86,"scale":0,"step":1}',
            }
        ),
        DPCode.C_F
        + "": SimpleNamespace(
            **{
                "code": DPCode.C_F + "",
                "type": "Enum",
                "values": '{"range":["C","F"]}',
            }
        ),
        DPCode.TEMP_CURRENT
        + "": SimpleNamespace(
            **{
                "code": DPCode.TEMP_CURRENT + "",
                "type": "Integer",
                "values": '{"unit":"C","min":-7,"max":98,"scale":0,"step":1}',
            }
        ),
    },
)

DEVICE_NOT_FOLLOWING_SPECS = create_tuya_device(
    "int_device_not_following_specs",
    "kt",
    {
        DPCode.SWITCH + "": False,
        DPCode.TEMP_SET + "": 20,
        DPCode.TEMP_CURRENT + "": 20,
        DPCode.C_F + "": "C",
    },
    {
        DPCode.SWITCH
        + "": SimpleNamespace(
            **{
                "code": DPCode.SWITCH + "",
                "type": "Boolean",
                "values": "{}",
            }
        ),
        DPCode.TEMP_SET
        + "": SimpleNamespace(
            **{
                "code": DPCode.TEMP_SET + "",
                "type": "Integer",
                "values": '{"unit":"C","min":"16","max":"86","scale":"0","step":"1"}',
            }
        ),
        DPCode.C_F
        + "": SimpleNamespace(
            **{
                "code": DPCode.C_F + "",
                "type": "Enum",
                "values": '{"range":["C","F"]}',
            }
        ),
        DPCode.TEMP_CURRENT
        + "": SimpleNamespace(
            **{
                "code": DPCode.TEMP_CURRENT + "",
                "type": "Integer",
                "values": '{"unit":"C","min":"-7","max":"98","scale":"0","step":"1"}',
            }
        ),
    },
)


@pytest.mark.parametrize(
    "device",
    [DEVICE_FOLLOWING_SPECS, DEVICE_NOT_FOLLOWING_SPECS],
)
def test_entity_climate_build(
    device: TuyaDevice,
):
    """Test TuyaClimateEntity ctor with different specs, matching or diverging from the doc."""

    tuya_climate_entity = TuyaClimateEntity(
        device,
        MagicMock(),
        CLIMATE_DESCRIPTIONS[device.category],
    )

    assert tuya_climate_entity._attr_target_temperature_step == 1
