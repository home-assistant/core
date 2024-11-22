"""The microBees Coordinator."""

from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
import json
import logging

import aiohttp
from microBeesPy import (
    Actuator,
    Bee,
    MicroBees,
    MicroBeesException,
    MicrobeesMqtt,
    Sensor,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class MicroBeesCoordinatorData:
    """Container for MicroBees data managed by the Coordinator."""

    bees: dict[int, Bee]
    actuators: dict[int, Actuator]
    sensors: dict[int, Sensor]


class MicroBeesUpdateCoordinator(DataUpdateCoordinator[MicroBeesCoordinatorData]):
    """Coordinator to manage MicroBees data and MQTT integration."""

    def __init__(
        self, hass: HomeAssistant, microbees: MicroBees, mqtt_client: MicrobeesMqtt
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="microBees Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self.microbees = microbees
        self.mqtt_client = mqtt_client
        self.initial_data_loaded = False
        self.mqtt_connected = False

        # Set the MQTT callback for incoming messages
        self.mqtt_client.on_message_callback = self.handle_mqtt_message

    async def async_start(self) -> None:
        """Start the coordinator by loading initial data and connecting MQTT."""
        await self._load_initial_data()
        if self.mqtt_client.connect():
            self.mqtt_connected = True

    async def async_shutdown(self) -> None:
        """Disconnect the MQTT client during shutdown."""
        self.mqtt_connected = False
        self.mqtt_client.disconnect()

    async def _load_initial_data(self) -> None:
        """Fetch the initial data from the MicroBees API."""
        try:
            bees = await self.microbees.getBees()
            self._process_bees(bees)
            self.initial_data_loaded = True
        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from err
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except MicroBeesException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _process_bees(self, bees: list[Bee]) -> None:
        """Process bees data and update the internal state."""
        bees_dict = {}
        actuators_dict = {}
        sensors_dict = {}
        for bee in bees:
            bees_dict[bee.id] = bee
            for actuator in bee.actuators:
                actuators_dict[actuator.id] = actuator
            for sensor in bee.sensors:
                sensors_dict[sensor.id] = sensor

        self.data = MicroBeesCoordinatorData(
            bees=bees_dict, actuators=actuators_dict, sensors=sensors_dict
        )

    async def handle_mqtt_message(self, message) -> None:
        """Handle incoming MQTT messages and update the internal state."""
        try:
            payload = json.loads(message.payload.decode())
            device_id = payload.get("id")

            if device_id in self.data.bees:
                self._update_device(device_id, payload)
            else:
                self._add_new_device(device_id, payload)

        except json.JSONDecodeError:
            _LOGGER.error("Failed to decode MQTT message: %s", message.payload.decode())
        except KeyError as err:
            _LOGGER.error("Key error handling MQTT message: %s", err)
        except TypeError as err:
            _LOGGER.error("Type error handling MQTT message: %s", err)
        except ValueError as err:
            _LOGGER.error("Value error handling MQTT message: %s", err)

    def _update_device(self, device_id: int, payload: dict) -> None:
        """Update an existing device based on MQTT payload."""

        for sensor_update in payload.get("sensors", []):
            sensor_id = sensor_update["id"]
            self.data.sensors[sensor_id] = Sensor(
                id=sensor_id,
                name=sensor_update["name"],
                lastUpdate=sensor_update["lastUpdate"],
                deviceID=sensor_update["deviceID"],
                prototypeID=sensor_update["prototypeID"],
                prototypeName=sensor_update["prototypeName"],
                device_type=sensor_update["device_type"],
                dc_type=sensor_update.get("dc_type"),
                unit=sensor_update.get("unit"),
                payload=sensor_update.get("payload"),
                value=sensor_update.get("value"),
            )

        for actuator_update in payload.get("actuators", []):
            actuator_id = actuator_update["id"]
            self.data.actuators[actuator_id] = Actuator(
                id=actuator_id,
                name=actuator_update["name"],
                prototypeName=actuator_update["prototypeName"],
                deviceID=actuator_update["deviceID"],
                configuration=actuator_update["configuration"],
                starred=actuator_update["starred"],
                uptime=actuator_update["uptime"],
                sensorID=actuator_update["sensorID"],
                payload=actuator_update.get("payload"),
                value=actuator_update.get("value"),
            )

        self.data = MicroBeesCoordinatorData(
            bees=self.data.bees,
            actuators=self.data.actuators,
            sensors=self.data.sensors,
        )

        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    def _add_new_device(self, device_id: int, payload: dict) -> None:
        """Add a new device based on MQTT payload."""
        new_bee = Bee(
            id=device_id,
            label=payload["label"],
            serial=payload["serial"],
            gate_serial=payload["gate_serial"],
            gate_id=payload["gate_id"],
            lastUpdate=payload["lastUpdate"],
            name=payload["name"],
            active=payload["active"],
            productID=payload["productID"],
            prototypeName=payload["prototypeName"],
            rssi=payload["rssi"],
            lastActivation=payload["lastActivation"],
            icon=payload["icon"],
            configuration=payload["configuration"],
            instanceData=payload["instanceData"],
            sensors=[],
            actuators=[],
        )

        for sensor_data in payload.get("sensors", []):
            sensor_id = sensor_data["id"]
            new_bee.sensors[sensor_id] = Sensor(
                id=sensor_id,
                name=sensor_data["name"],
                lastUpdate=sensor_data["lastUpdate"],
                deviceID=sensor_data["deviceID"],
                prototypeID=sensor_data["prototypeID"],
                prototypeName=sensor_data["prototypeName"],
                device_type=sensor_data["device_type"],
                dc_type=sensor_data.get("dc_type"),
                unit=sensor_data.get("unit"),
                payload=sensor_data.get("payload"),
                value=sensor_data.get("value"),
            )

        for actuator_data in payload.get("actuators", []):
            actuator_id = actuator_data["id"]
            new_bee.actuators[actuator_id] = Actuator(
                id=actuator_id,
                name=actuator_data["name"],
                prototypeName=actuator_data["prototypeName"],
                deviceID=actuator_data["deviceID"],
                configuration=actuator_data["configuration"],
                starred=actuator_data["starred"],
                uptime=actuator_data["uptime"],
                sensorID=actuator_data["sensorID"],
                payload=actuator_data.get("payload"),
                value=actuator_data.get("value"),
            )

        self.data.bees[device_id] = new_bee

        self.data = MicroBeesCoordinatorData(
            bees=self.data.bees,
            actuators=self.data.actuators,
            sensors=self.data.sensors,
        )

        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    async def _async_update_data(self) -> MicroBeesCoordinatorData:
        """Fetch data for Home Assistant update loop."""
        if not self.initial_data_loaded:
            await self._load_initial_data()
        return self.data
