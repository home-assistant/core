"""
Sensor Platform Device for Wiser System.

https://github.com/asantaga/wiserHomeAssistantPlatform
Angelosantagata@gmail.com

"""

from homeassistant.const import ATTR_BATTERY_LEVEL, DEVICE_CLASS_BATTERY
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    _LOGGER,
    DATA,
    DOMAIN,
    ROOMSTAT_FULL_BATTERY_LEVEL,
    ROOMSTAT_MIN_BATTERY_LEVEL,
    SIGNAL_STRENGTH_ICONS,
    TRV_FULL_BATTERY_LEVEL,
    TRV_MIN_BATTERY_LEVEL,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize the entry."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA]  # Get Handler
    wiser_devices = []

    # Add device sensors, only if there are some.
    if data.wiserhub.getDevices() is not None:
        for device in data.wiserhub.getDevices():
            wiser_devices.append(
                WiserDeviceSensor(data, device.get("id"), device.get("ProductType"))
            )

            # Add based on device type due to battery values sometimes not showing.
            # until sometime after a hub restart
            if device.get("ProductType") in ["iTRV", "RoomStat"]:
                wiser_devices.append(
                    WiserBatterySensor(data, device.get("id"), sensor_type="Battery")
                )

    # Add cloud status sensor
    wiser_devices.append(WiserSystemCloudSensor(data, sensor_type="Cloud Sensor"))
    # Add operation sensor
    wiser_devices.append(
        WiserSystemOperationModeSensor(data, sensor_type="Operation Mode")
    )
    # Add heating circuit sensor
    wiser_devices.append(WiserSystemCircuitState(data, sensor_type="HEATING"))
    # Don't display Hotwater if hotwater not supported
    # https://github.com/asantaga/wiserHomeAssistantPlatform/issues/8
    if data.wiserhub.getHotwater() is not None:
        wiser_devices.append(WiserSystemCircuitState(data, sensor_type="HOTWATER"))

    async_add_entities(wiser_devices, True)


class WiserSensor(Entity):
    """Definition of a Wiser sensor."""

    def __init__(self, config_entry, device_id=0, sensor_type=""):
        """Initialize the sensor."""
        self.data = config_entry
        self._device_id = device_id
        self._device_name = None
        self._sensor_type = sensor_type
        self._state = None

    #
    @staticmethod
    def calculate_device_battery_pct(device_type, device_voltage):
        """

        Calculate device battery levels.

        :param device_type:
        :param device_voltage:
        :return:

        """

        # Return 0 if not iTRV or RoomStat, should never be
        if device_type not in ("iTRV", "RoomStat"):
            return 0

        if device_type == "iTRV":
            return min(
                100,
                int(
                    (
                        (device_voltage - TRV_MIN_BATTERY_LEVEL)
                        / (TRV_FULL_BATTERY_LEVEL - TRV_MIN_BATTERY_LEVEL)
                    )
                    * 100
                ),
            )
        # If not TRV then RoomStat
        return min(
            100,
            int(
                (
                    (device_voltage - ROOMSTAT_MIN_BATTERY_LEVEL)
                    / (ROOMSTAT_FULL_BATTERY_LEVEL - ROOMSTAT_MIN_BATTERY_LEVEL)
                )
                * 100
            ),
        )

    async def async_update(self):
        """Async Update."""
        _LOGGER.debug("%s device update requested", self._device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device_name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug("%s device state requested", self.name)
        return self._state

    @property
    def unique_id(self):
        """Return uniqueid."""
        return f"{self._sensor_type}-{self._device_id}"

    async def async_added_to_hass(self):
        """Subscribe for update from the hub."""

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, "WiserHubUpdateMessage", async_update_state
            )
        )


class WiserBatterySensor(WiserSensor):
    """Definition of a battery sensor for wiser iTRVs and RoomStats."""

    def __init__(self, data, device_id=0, sensor_type=""):
        """Initialise the battery sensor."""

        super().__init__(data, device_id, sensor_type)
        self._device_name = self.get_device_name()
        # Set default state to unknown to show this value if battery info
        # cannot be read.
        self._state = "Unknown"
        self._battery_voltage = 0
        self._battery_level = None
        _LOGGER.info("%s device init", self._device_name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()

        device = self.data.wiserhub.getDevice(self._device_id)

        # Set battery info
        self._battery_level = device.get("BatteryLevel")
        self._battery_voltage = device.get("BatteryVoltage")

        if self._battery_voltage and self._battery_voltage > 0:
            self._state = self.calculate_device_battery_pct(
                device.get("ProductType"), self._battery_voltage
            )

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "%"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the battery."""
        attrs = {}
        if self._battery_voltage and self._battery_voltage > 0:
            attrs["battery_voltage"] = str(self._battery_voltage / 10)
            attrs[ATTR_BATTERY_LEVEL] = (
                self.data.wiserhub.getDevice(self._device_id).get("BatteryLevel")
                or None
            )
        return attrs

    def get_device_name(self):
        """Return the name of the Device."""
        product_type = str(
            self.data.wiserhub.getDevice(self._device_id).get("ProductType") or ""
        )

        # Only iTRVs and RoomStats have batteries
        if product_type == "iTRV":
            # Multiple ones get automagically number _n by HA
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + self.data.wiserhub.getDeviceRoom(self._device_id)["roomName"]
                + " Battery Level"
            )
        elif product_type == "RoomStat":
            # Usually only one per room
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + self.data.wiserhub.getDeviceRoom(self._device_id)["roomName"]
                + " Battery Level"
            )
        else:
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + str(
                    self.data.wiserhub.getDevice(self._device_id).get("SerialNumber")
                    or "" + " Battery Level"
                )
            )
        return device_name

    @property
    def device_info(self):
        """Return device specific attributes."""
        product_type = self.data.wiserhub.getDevice(self._device_id).get("ProductType")
        return {"identifiers": {(DOMAIN, f"{product_type}-{self._device_id}")}}


class WiserDeviceSensor(WiserSensor):
    """Definition of Wiser Device Sensor."""

    def __init__(self, data, device_id=0, sensor_type=""):
        """Initialise the device sensor."""

        super().__init__(data, device_id, sensor_type)
        self._device_name = self.get_device_name()
        self._battery_voltage = 0
        self._battery_level = None
        self._battery_percent = 0
        _LOGGER.info("%s device init", self._device_name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        self._state = self.data.wiserhub.getDevice(self._device_id).get(
            "DisplayedSignalStrength"
        )

    @property
    def device_info(self):
        """Return device specific attributes."""
        identifier = None

        if (
            self.data.wiserhub.getDevice(self._device_id).get("ProductType")
            == "Controller"
        ):
            info = {"identifiers": {(DOMAIN, self.data.unique_id)}}
        elif (
            self.data.wiserhub.getDevice(self._device_id).get("ProductType")
            == "SmartPlug"
        ):
            # combine sensor for smartplug with smartplug device
            identifier = f"{self._device_name}-{self._device_id}"

            info = {"identifiers": {(DOMAIN, identifier)}}
        else:
            info = {
                "name": self.name,
                "identifiers": {(DOMAIN, self.unique_id)},
                "manufacturer": "Drayton Wiser",
                "model": self.data.wiserhub.getDevice(self._device_id).get(
                    "ProductType"
                ),
            }
        return info

    def get_device_name(self):
        """Return the name of the Device."""
        product_type = str(
            self.data.wiserhub.getDevice(self._device_id).get("ProductType") or ""
        )

        if product_type == "Controller":
            device_name = "Wiser Heathub"  # Only ever one of these
        elif product_type == "iTRV":
            # Multiple ones get automagically number _n by HA
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + self.data.wiserhub.getDeviceRoom(self._device_id)["roomName"]
            )
        elif product_type == "RoomStat":
            # Usually only one per room
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + self.data.wiserhub.getDeviceRoom(self._device_id)["roomName"]
            )
        elif product_type == "SmartPlug":
            device_name = (
                "Wiser " + self.data.wiserhub.getSmartPlug(self._device_id)["Name"]
            )
        else:
            device_name = (
                "Wiser "
                + product_type
                + "-"
                + str(
                    self.data.wiserhub.getDevice(self._device_id).get("SerialNumber")
                    or ""
                )
            )
        return device_name

    @property
    def icon(self):
        """Return icon for signal strength."""
        try:
            return SIGNAL_STRENGTH_ICONS[
                self.data.wiserhub.getDevice(self._device_id).get(
                    "DisplayedSignalStrength"
                )
            ]
        except KeyError:
            # Handle anything else as no signal
            return SIGNAL_STRENGTH_ICONS["NoSignal"]

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        _LOGGER.debug("State attributes for %s %s", self._device_id, self._sensor_type)
        attrs = {}
        device_data = self.data.wiserhub.getDevice(self._device_id)

        # Generic attributes
        attrs["vendor"] = "Drayton Wiser"
        attrs["product_type"] = device_data.get("ProductType")
        attrs["model_identifier"] = device_data.get("ModelIdentifier")
        attrs["device_lock_enabled"] = device_data.get("DeviceLockEnabled")
        attrs["displayed_signal_strength"] = device_data.get("DisplayedSignalStrength")
        attrs["firmware"] = device_data.get("ActiveFirmwareVersion")
        attrs["serial_number"] = device_data.get("SerialNumber")

        # if controller then add the zigbee data to the controller info
        if device_data.get("ProductType") == "Controller":
            attrs["zigbee_channel"] = (
                self.data.wiserhub.getHubData().get("Zigbee").get("NetworkChannel")
            )

        # Network Data
        attrs["node_id"] = device_data.get("NodeId")
        attrs["displayed_signal_strength"] = device_data.get("DisplayedSignalStrength")

        if self._sensor_type in ["RoomStat", "iTRV"]:
            attrs["parent_node_id"] = device_data.get("ParentNodeId")
            # hub route
            if device_data.get("ParentNodeId") == 0:

                attrs["hub_route"] = "direct"
            else:
                attrs["hub_route"] = "repeater"

        if device_data.get("ReceptionOfDevice") is not None:
            attrs["device_reception_RSSI"] = device_data.get("ReceptionOfDevice").get(
                "Rssi"
            )
            attrs["device_reception_LQI"] = device_data.get("ReceptionOfDevice").get(
                "Lqi"
            )

        if device_data.get("ReceptionOfController") is not None:
            attrs["controller_reception_RSSI"] = device_data.get(
                "ReceptionOfController"
            ).get("Rssi")
            attrs["device_reception_LQI"] = device_data.get(
                "ReceptionOfController"
            ).get("Lqi")

        if self._sensor_type in ["RoomStat", "iTRV"] and device_data.get(
            "BatteryVoltage"
        ):
            self._battery_level = device_data.get("BatteryLevel")
            self._battery_voltage = device_data.get("BatteryVoltage")
            self._battery_percent = 0
            if self._battery_voltage and self._battery_voltage > 0:

                self._battery_percent = self.calculate_device_battery_pct(
                    self._sensor_type, self._battery_voltage
                )

            attrs["battery_voltage"] = str(self._battery_voltage / 10)
            attrs["battery_percent"] = self._battery_percent
            attrs["battery_level"] = device_data.get("BatteryLevel")

        # Other
        if self._sensor_type == "RoomStat":
            attrs["humidity"] = self.data.wiserhub.getRoomStatData(self._device_id).get(
                "MeasuredHumidity"
            )

        return attrs


class WiserSystemCircuitState(WiserSensor):
    """Definition of a Hotwater/Heating circuit state sensor."""

    def __init__(self, data, device_id=0, sensor_type=""):
        """Initialise the CircuitState Sensor."""

        super().__init__(data, device_id, sensor_type)
        self._device_name = self.get_device_name()
        _LOGGER.info("%s device init", self._device_name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._sensor_type == "HEATING":
            self._state = self.data.wiserhub.getHeatingRelayStatus()
        else:
            self._state = self.data.wiserhub.getHotwaterRelayStatus()

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.data.unique_id)},
        }

    def get_device_name(self):
        """Return the name of the Device."""
        if self._sensor_type == "HEATING":
            return "Wiser Heating"
        return "Wiser Hot Water"

    @property
    def icon(self):
        """Return icon."""
        if self._sensor_type == "HEATING":
            if self._state == "Off":
                return "mdi:radiator-disabled"
            return "mdi:radiator"

        # Hot water circuit
        if self._state == "Off":
            return "mdi:water-off"
        return "mdi:water"

    @property
    def device_state_attributes(self):
        """Return additional info."""
        attrs = {}
        if self._sensor_type == "HEATING":
            heating_channels = self.data.wiserhub.getHeatingChannels()
            for heating_channel in heating_channels:
                channel_name = heating_channel.get("Name")
                channel_pct_dmd = heating_channel.get("PercentageDemand")
                channel_room_ids = heating_channel.get("RoomIds")
                attr_name = f"percentage_demand_{channel_name}"
                attrs[attr_name] = channel_pct_dmd
                attr_name_2 = f"room_ids_{channel_name}"
                attrs[attr_name_2] = channel_room_ids
        return attrs


class WiserSystemCloudSensor(WiserSensor):
    """Sensor to display the status of the Wiser Cloud."""

    def __init__(self, data, device_id=0, sensor_type=""):
        """Initialise the cloud sensor."""

        super().__init__(data, device_id, sensor_type)
        self._device_name = self.get_device_name()
        _LOGGER.info("%s device init", self._device_name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        self._state = self.data.wiserhub.getSystem().get("CloudConnectionStatus")

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.data.unique_id)},
        }

    @staticmethod
    def get_device_name():
        """Return the name of the Device."""
        return "Wiser Cloud Status"

    @property
    def icon(self):
        """Return icon."""
        if self._state == "Connected":
            return "mdi:cloud-check"
        return "mdi:cloud-alert"


class WiserSystemOperationModeSensor(WiserSensor):
    """Sensor for the Wiser Operation Mode (Away/Normal etc)."""

    def __init__(self, data, device_id=0, sensor_type=""):
        """Initialise the operation mode sensor."""

        super().__init__(data, device_id, sensor_type)
        self._device_name = self.get_device_name()
        self._override_type = self.data.wiserhub.getSystem().get("OverrideType")
        self._away_temperature = self.data.wiserhub.getSystem().get(
            "AwayModeSetPointLimit"
        )
        _LOGGER.info("%s device init", self._device_name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        self._override_type = self.data.wiserhub.getSystem().get("OverrideType")
        self._away_temperature = self.data.wiserhub.getSystem().get(
            "AwayModeSetPointLimit"
        )
        self._state = self.mode()

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.data.unique_id)},
        }

    def mode(self):
        """Return mode."""
        if self._override_type and self._override_type == "Away":
            return "Away"
        return "Normal"

    @staticmethod
    def get_device_name():
        """Return the name of the Device."""
        return "Wiser Operation Mode"

    @property
    def icon(self):
        """Return icon."""
        if self.mode() == "Normal":
            return "mdi:check"
        return "mdi:alert"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {"AwayModeTemperature": -1.0}
        if self._away_temperature:
            try:
                attrs["AwayModeTemperature"] = round(self._away_temperature / 10.0, 1)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "Exception Unexpected value for awayTemperature %s",
                    self._away_temperature,
                )
        return attrs
