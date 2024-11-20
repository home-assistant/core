"""Common stuff for Comelit SimpleHome tests."""

from aiocomelit import ComelitVedoAreaObject, ComelitVedoZoneObject
from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import (
    CLIMATE,
    COVER,
    IRRIGATION,
    LIGHT,
    OTHER,
    SCENARIO,
    VEDO,
    WATT,
    AlarmAreaState,
    AlarmZoneState,
)

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PORT: 80,
                CONF_PIN: 1234,
            },
            {
                CONF_HOST: "fake_vedo_host",
                CONF_PORT: 8080,
                CONF_PIN: 1234,
                CONF_TYPE: VEDO,
            },
        ]
    }
}

MOCK_USER_BRIDGE_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_USER_VEDO_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][1]

FAKE_PIN = 5678

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
