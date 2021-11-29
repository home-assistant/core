"""Test the Ecowitt integration."""
import asyncio


class EcoWittListenerMock:
    """Create Mock pyecowitt listener."""

    def __init__(self, port):
        """Construct a false EcoWittListener."""
        # API Constants
        self.port = port
        self.data_valid = True
        self._station_type = "Mocked"
        self._station_freq = "Mocked"
        self._station_model = "Mocked"
        self.data_ready = True
        self.windchill_type = 2
        self.sensors = []
        self.new_sensor_cb = None

    async def listen(self):
        """Listen and process."""

        while True:
            await asyncio.sleep(60)

    async def wait_for_valid_data(self):
        """Wait for valid data, then return true."""
        return self.data_valid

    async def stop(self):
        """Fake a stop of the webserver."""
        self.data_valid = True
        return

    def set_windchill(self, wind):
        """Set a windchill mode, [012]."""
        if wind < 0 or wind > 2:
            return
        self.windchill_type = wind

    def list_sensor_keys(self):
        """List all available sensors by key."""
        sensor_list = []
        for sensor in self.sensors:
            sensor_list.append(sensor.get_key())
        return sensor_list

    def register_listener(self, function):
        """Register a listener."""
        self.data_valid = True
        return

    def int_new_sensor_cb(self):
        """Create Internal new sensor callback."""
        if self.new_sensor_cb is None:
            return
        self.new_sensor_cb()
