"""Common stuff for Comelit SimpleHome tests."""

from aiocomelit.api import (
    AlarmDataObject,
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
    CLIMATE: {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Climate0",
            status=0,
            human_status="off",
            type="climate",
            val=[
                [221, 0, "U", "M", 50, 0, 0, "U"],
                [650, 0, "U", "M", 500, 0, 0, "U"],
                [0, 0],
            ],
            protected=0,
            zone="Living room",
            power=0.0,
            power_unit=WATT,
        ),
    },
    COVER: {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Cover0",
            status=0,
            human_status="stopped",
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
    OTHER: {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Switch0",
            status=0,
            human_status="off",
            type="other",
            val=0,
            protected=0,
            zone="Bathroom",
            power=0.0,
            power_unit=WATT,
        ),
    },
    IRRIGATION: {},
    SCENARIO: {},
}

VEDO_DEVICE_QUERY = AlarmDataObject(
    alarm_areas={
        0: ComelitVedoAreaObject(
            index=0,
            name="Area0",
            p1=True,
            p2=True,
            ready=False,
            armed=0,
            alarm=False,
            alarm_memory=False,
            sabotage=False,
            anomaly=False,
            in_time=False,
            out_time=False,
            human_status=AlarmAreaState.DISARMED,
        )
    },
    alarm_zones={
        0: ComelitVedoZoneObject(
            index=0,
            name="Zone0",
            status_api="0x000",
            status=0,
            human_status=AlarmZoneState.REST,
        )
    },
)
