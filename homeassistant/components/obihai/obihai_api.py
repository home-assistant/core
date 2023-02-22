"""Support for Obihai Sensors."""
from __future__ import annotations

from pyobihai import PyObihai

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, LOGGER, OBIHAI


def get_pyobihai(
    host: str,
    username: str,
    password: str,
) -> PyObihai:
    """Retrieve an authenticated PyObihai."""
    return PyObihai(host, username, password)


def validate_auth(
    host: str,
    username: str,
    password: str,
) -> bool:
    """Test if the given setting works as expected."""
    obi = get_pyobihai(host, username, password)

    login = obi.check_account()
    if not login:
        LOGGER.debug("Invalid credentials")
        return False

    return True


class ObihaiConnection:
    """Contains a list of Obihai Sensors."""

    def __init__(
        self,
        host: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
    ) -> None:
        """Store configuration."""
        self.sensors: list[ObihaiServiceSensors] = []
        self.host = host
        self.username = username
        self.password = password

    def update(self) -> bool:
        """Validate connection and retrieve a list of sensors."""
        pyobihai = get_pyobihai(self.host, self.username, self.password)

        if not pyobihai.check_account():
            return False

        serial = pyobihai.get_device_serial()
        services = pyobihai.get_state()
        line_services = pyobihai.get_line_state()
        call_direction = pyobihai.get_call_direction()

        for key in services:
            self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        if line_services is not None:
            for key in line_services:
                self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        for key in call_direction:
            self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        return True


class ObihaiServiceSensors(SensorEntity):
    """Get the status of each Obihai Lines."""

    def __init__(self, pyobihai, serial, service_name):
        """Initialize monitor sensor."""
        self._service_name = service_name
        self._state = None
        self._name = f"{OBIHAI} {self._service_name}"
        self._pyobihai = pyobihai
        self._unique_id = f"{serial}-{self._service_name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return if sensor is available."""
        if self._state is not None:
            return True
        return False

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the device class for uptime sensor."""
        if self._service_name == "Last Reboot":
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def icon(self):
        """Return an icon."""
        if self._service_name == "Call Direction":
            if self._state == "No Active Calls":
                return "mdi:phone-off"
            if self._state == "Inbound Call":
                return "mdi:phone-incoming"
            return "mdi:phone-outgoing"
        if "Caller Info" in self._service_name:
            return "mdi:phone-log"
        if "Port" in self._service_name:
            if self._state == "Ringing":
                return "mdi:phone-ring"
            if self._state == "Off Hook":
                return "mdi:phone-in-talk"
            return "mdi:phone-hangup"
        if "Service Status" in self._service_name:
            if "OBiTALK Service Status" in self._service_name:
                return "mdi:phone-check"
            if self._state == "0":
                return "mdi:phone-hangup"
            return "mdi:phone-in-talk"
        if "Reboot Required" in self._service_name:
            if self._state == "false":
                return "mdi:restart-off"
            return "mdi:restart-alert"
        return "mdi:phone"

    def update(self) -> bool:
        """Update the sensor."""
        if self._pyobihai.check_account():
            services = self._pyobihai.get_state()

            if self._service_name in services:
                self._state = services.get(self._service_name)

            services = self._pyobihai.get_line_state()

            if services is not None and self._service_name in services:
                self._state = services.get(self._service_name)

            call_direction = self._pyobihai.get_call_direction()

            if self._service_name in call_direction:
                self._state = call_direction.get(self._service_name)

            return True

        self._state = None
        return False
