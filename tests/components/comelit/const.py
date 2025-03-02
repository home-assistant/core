"""Common stuff for Comelit SimpleHome tests."""

from aiocomelit import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import (
    CLIMATE,
    COVER,
    IRRIGATION,
    LIGHT,
    OTHER,
    SCENARIO,
    WATT,
    AlarmAreaState,
    AlarmZoneState,
)

BRIDGE_HOST = "fake_bridge_host"
BRIDGE_PORT = 80
BRIDGE_PIN = 1234

VEDO_HOST = "fake_vedo_host"
VEDO_PORT = 8080
VEDO_PIN = 5678

FAKE_PIN = 0000

BRIDGE_DEVICE_QUERY = {
    CLIMATE: {},
    COVER: {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Cover0",
            status=0,
            human_status="closed",
            type="cover",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        )
    },
    LIGHT: {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Light0",
            status=0,
            human_status="off",
            type="light",
            val=0,
            protected=0,
            zone="Bathroom",
            power=0.0,
            power_unit=WATT,
        )
    },
    OTHER: {},
    IRRIGATION: {},
    SCENARIO: {},
}

VEDO_DEVICE_QUERY = {
    "aree": {
        0: ComelitVedoAreaObject(
            index=0,
            name="Area0",
            p1=True,
            p2=False,
            ready=False,
            armed=False,
            alarm=False,
            alarm_memory=False,
            sabotage=False,
            anomaly=False,
            in_time=False,
            out_time=False,
            human_status=AlarmAreaState.UNKNOWN,
        )
    },
    "zone": {
        0: ComelitVedoZoneObject(
            index=0,
            name="Zone0",
            status_api="0x000",
            status=0,
            human_status=AlarmZoneState.REST,
        )
    },
}
