"""Integration test for the Victron Venus hub, devices and sensors.

This tests fakes a real MQTT device, and simulates the messages that would be published by the device.
"""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.victronvenus import (
    async_setup_entry as vv_async_setup_entry,
)
from homeassistant.components.victronvenus.const import (
    CONF_INSTALLATION_ID,
    CONF_SERIAL,
)
from homeassistant.components.victronvenus.sensor import (
    async_setup_entry as vv_async_setup_entry_sensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant


class _MockGMQTTClient:
    """A mock GMQTT client to simulate the behaviour of a real device."""

    def __init__(self) -> None:
        """Initialize internal member variables to simulate a GMQTT client."""

        self.connected = False
        self.subscriptions = {}
        self.published_messages = []
        self.on_connect = None
        self.on_message = None
        self._isalive = False

    async def connect(self, *args, **kwargs):
        self.connected = True
        return self

    def disconnect(self):
        self.connected = False

    def subscribe(self, topic, qos=0):
        self.subscriptions[topic] = qos

    def unsubscribe(self, topic):
        self.subscriptions.pop(topic, None)

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published_messages.append(
            {"topic": topic, "payload": payload, "qos": qos, "retain": retain}
        )
        if topic == "R/INSTALLID/keepalive":
            self._isalive = True

    @property
    def is_connected(self):
        return self.connected

    async def sim_published_messages(self):
        if self.on_message is None:
            return
        await self.on_message(
            self, "N/INSTALLID/system/0/Serial", b'{"value":"INSTALLID"}', 0, False
        )
        if (
            self._isalive
        ):  # we only publish the other messages if the keepalive message was sent
            # system - device 0
            await self.on_message(
                self,
                "N/INSTALLID/system/0/Ac/Grid/NumberOfPhases",
                b'{"value":1}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/system/0/Ac/ConsumptionOnInput/L1/Power",
                b'{"value":1000.0}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/system/0/Ac/ConsumptionOnOutput/L1/Power",
                b'{"value":500.0}',
                0,
                False,
            )

            # grid - device 100

            await self.on_message(
                self,
                "N/INSTALLID/grid/100/ProductName",
                b'{"value":"MyGrid"}',
                0,
                False,
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/Serial", b'{"value":"123"}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/ProductId", b'{"value":1}', 0, False
            )

            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/Voltage", b'{"value":230.0}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/Power", b'{"value":1000.0}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/Current", b'{"value":4.3}', 0, False
            )
            await self.on_message(
                self,
                "N/INSTALLID/grid/100/Ac/Energy/Forward",
                b'{"value":1000.0}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/grid/100/Ac/Energy/Reverse",
                b'{"value":0.0}',
                0,
                False,
            )

            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/L1/Voltage", b'{"value":230.0}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/L1/Power", b'{"value":1000.0}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/grid/100/Ac/L1/Current", b'{"value":4.3}', 0, False
            )

            # battery - device 200
            await self.on_message(
                self,
                "N/INSTALLID/battery/200/ProductName",
                b'{"value":"MyBattery"}',
                0,
                False,
            )
            await self.on_message(
                self, "N/INSTALLID/battery/200/Serial", b'{"value":"456"}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/battery/200/ProductId", b'{"value":1}', 0, False
            )

            await self.on_message(
                self,
                "N/INSTALLID/battery/200/Dc/0/Voltage",
                b'{"value":50.0}',
                0,
                False,
            )
            await self.on_message(
                self, "N/INSTALLID/battery/200/Dc/0/Current", b'{"value":1.0}', 0, False
            )
            await self.on_message(
                self, "N/INSTALLID/battery/200/Dc/0/Power", b'{"value":50.0}', 0, False
            )

            await self.on_message(
                self,
                "N/INSTALLID/battery/200/History/DischargedEnergy",
                b'{"value":50.0}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/battery/200/History/ChargedEnergy",
                b'{"value":50.0}',
                0,
                False,
            )
            await self.on_message(
                self, "N/INSTALLID/battery/200/Soc", b'{"value":50.0}', 0, False
            )

            # solar charger - device 300
            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/ProductName",
                b'{"value":"MyMPPT"}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/Serial",
                b'{"value":"789"}',
                0,
                False,
            )
            await self.on_message(
                self, "N/INSTALLID/solarcharger/300/ProductId", b'{"value":1}', 0, False
            )

            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/Dc/0/Voltage",
                b'{"value":250.0}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/Dc/0/Current",
                b'{"value":0.5}',
                0,
                False,
            )

            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/Yield/User",
                b'{"value":2000.0}',
                0,
                False,
            )
            await self.on_message(
                self,
                "N/INSTALLID/solarcharger/300/History/Daily/0/MaxPower",
                b'{"value":4400.0}',
                0,
                False,
            )

            # indicate that we have published a full set
            await self.on_message(
                self,
                "N/INSTALLID/full_publish_completed",
                b'{"value":123456}',
                0,
                False,
            )


_client = _MockGMQTTClient()


@pytest.fixture
def config_entry_for_hubtest() -> ConfigEntry:
    """Create a fake config entry for the hub test."""

    return ConfigEntry(
        version=1,
        domain="victronvenus",
        title="Victron Installation INSTALLID",
        discovery_keys=[],
        minor_version=None,
        options=None,
        source=None,
        unique_id=None,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 1883,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
            CONF_INSTALLATION_ID: "INSTALLID",
            CONF_SERIAL: None,
        },
    )


def mock_async_add_entities(enttity):
    """Do nothing stub for async_add_entities."""


async def mock_connect(self):
    "Intercept the real connect method and replace it with a mock."
    self._client = _client
    await self._client.connect()
    return self._client


async def mock_async_forward_entry_setups(self, entry, platforms):
    """Instead of home assistant forwarding the entry setups, we will call the setup directly."""
    await vv_async_setup_entry_sensor(entry.hass, entry, mock_async_add_entities)


def mock_entity_async_write_ha_state(self):
    """Do nothing stub for async_write_ha_state."""


async def __broadcast_loop():
    """Broadcast messages to simulate the victron device messages. Repeat 10 times, yielding between each call."""
    for _i in range(10):  # broadcast 10 times
        await _client.sim_published_messages()
        await asyncio.sleep(0)


def test_hub_device_sensor_integration(
    hass: HomeAssistant, config_entry_for_hubtest: ConfigEntry
) -> None:
    """Tests the integration of the hub, devices and sensors, by simulating fake MQTT messages."""

    with (
        patch(
            "homeassistant.components.victronvenus.victronvenus_hub.VictronVenusHub.connect",
            new=mock_connect,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new=mock_async_forward_entry_setups,
        ),
        patch(
            "homeassistant.helpers.entity.Entity.async_write_ha_state",
            new=mock_entity_async_write_ha_state,
        ),
    ):
        config_entry = config_entry_for_hubtest
        config_entry.hass = hass
        setup_task = vv_async_setup_entry(hass, config_entry)
        broadcast_task = __broadcast_loop()
        alltasks = asyncio.gather(setup_task, broadcast_task, return_exceptions=False)
        hass.loop.run_until_complete(alltasks)

        hub = config_entry.runtime_data

        assert len(hub.devices) == 4, "Expected 4 devices to be created"

        for dev in hub.devices.values():
            sensors = dev.victron_sensors

            match dev.unique_id:
                case "INSTALLID_system_0":
                    assert dev.device_info["serial_number"] == "INSTALLID"
                    assert len(sensors) == 3, "Not all system sensors were created"

                case "INSTALLID_grid_100":
                    assert dev.device_info["identifiers"] == {
                        ("victronvenus", "INSTALLID_grid_100")
                    }
                    assert dev.device_info["model"] == "MyGrid"
                    assert dev.device_info["serial_number"] == "123"
                    assert dev.device_info["via_device"] == (
                        "victronvenus",
                        "INSTALLID_system_0",
                    )
                    assert len(sensors) == 8, "Not all grid sensors were created"

                case "INSTALLID_battery_200":
                    assert dev.device_info["identifiers"] == {
                        ("victronvenus", "INSTALLID_battery_200")
                    }
                    assert dev.device_info["model"] == "MyBattery"
                    assert dev.device_info["serial_number"] == "456"
                    assert dev.device_info["via_device"] == (
                        "victronvenus",
                        "INSTALLID_system_0",
                    )
                    assert len(sensors) == 6, "Not all battery sensors were created"

                case "INSTALLID_solarcharger_300":
                    assert dev.device_info["identifiers"] == {
                        ("victronvenus", "INSTALLID_solarcharger_300")
                    }
                    assert dev.device_info["model"] == "MyMPPT"
                    assert dev.device_info["serial_number"] == "789"
                    assert dev.device_info["via_device"] == (
                        "victronvenus",
                        "INSTALLID_system_0",
                    )
                    assert len(sensors) == 4, "Not all MPPT sensors were created"
