"""Parser for wiffi telegrams and server for wiffi devices."""
import asyncio
import json


class WiffiMetric:
    """Representation of wiffi metric reported in json telegram."""

    def __init__(self, data):
        """Initialize the instance."""
        self._id = int(data["name"])
        self._name = data["homematic_name"]
        self._metric_type = data["type"]
        self._description = data["desc"]
        self._unit_of_measurement = data["unit"]
        self._value = convert_value(data)

    @property
    def id(self):
        """Return integer based metric id.

        Called 'name' in the json telegram.
        """
        return int(self._id)

    @property
    def name(self):
        """Return metric name.

        Called 'homematic_name' in the json telegram.
        """
        return self._name

    @property
    def is_number(self):
        """Return true if the metric value type is a float number."""
        return self._metric_type == "number"

    @property
    def is_bool(self):
        """Return true if the metric value type is boolean."""
        return self._metric_type == "boolean"

    @property
    def is_string(self):
        """Return true if the metric value type is a string."""
        return self._metric_type == "string"

    @property
    def description(self):
        """Return metric description."""
        return self._description

    @property
    def unit_of_measurement(self):
        """Return metric unit of measurement.

        Returns an empty string for boolean and string metrics.
        """
        return self._unit_of_measurement

    @property
    def value(self):
        """Return the metric value.

        The returned value is either a float, bool or string depending on the
        metric type.
        """
        return self._value


def convert_value(var):
    """Convert the metric value from string into python type."""
    if var["type"] == "number":
        return float(var["value"])
    if var["type"] == "boolean":
        return var["value"] == "true"
    if var["type"] == "string":
        return var["value"]

    print("can't convert unknown type {} for var {}".format(var["type"], var["name"]))
    return None


class WiffiDevice:
    """Representation of wiffi device properties reported in the json telegram."""

    def __init__(self, moduletype, data):
        """Initialize the instance."""
        self._moduletype = moduletype
        self._mac_address = data["MAC-Adresse"]
        self._dest_ip = data["Homematic_CCU_ip"]
        self._wlan_ssid = data["WLAN_ssid"]
        self._wlan_signal_strength = float(data["WLAN_Signal_dBm"])
        self._sw_version = data["firmware"]

    @property
    def moduletype(self):
        """Return the wiffi device type, e.g. 'weatherman'."""
        return self._moduletype

    @property
    def mac_address(self):
        """Return the mac address of the wiffi device."""
        return self._mac_address

    @property
    def dest_ip(self):
        """Return the destination ip address for json telegrams."""
        return self._dest_ip

    @property
    def wlan_ssid(self):
        """Return the configured WLAN ssid."""
        return self._wlan_ssid

    @property
    def wlan_signal_strength(self):
        """Return the measured WLAN signal strength in dBm."""
        return self._wlan_signal_strength

    @property
    def sw_version(self):
        """Return the firmware revision string of the wiffi device."""
        return self._sw_version


class WiffiConnection:
    """Representation of a TCP connection between a wiffi device and the server.

    The following behaviour has been observed with weatherman firmware 107:
    For every json telegram which has to be sent by the wiffi device to the TCP
    server, a new TCP connection will be opened. After 1 json telegram has been
    transmitted, the connection will be closed again. The telegram is terminated
    by a 0x04 character. Therefore we read until we receive a 0x04 character and
    parse the whole telegram afterwards. Then we wait for the next telegram, but
    the connection will be closed by the wiffi device. Therefore we get an
    'IncompleteReadError exception which we will ignore. We don't close the
    connection on our own, because the behaviour that the wiffi device closes
    the connection after every telegram may change in the future.
    """

    def __init__(self, server):
        """Initialize the instance."""
        self._server = server

    async def __call__(self, reader, writer):
        """Process callback from the TCP server if a new connection has been opened."""
        while not reader.at_eof():
            try:
                data = await reader.readuntil(
                    b"\x04"
                )  # read until separator \x04 received
                await self.parse_msg(data[:-1])  # omit separator with [:-1]
            except asyncio.streams.IncompleteReadError:
                pass

    async def parse_msg(self, raw_data):
        """Parse received telegram which is terminated by 0x04."""
        data = json.loads(raw_data.decode("utf-8"))

        moduletype = data["modultyp"]
        systeminfo = data["Systeminfo"]

        metrics = []
        for var in data["vars"]:
            metrics.append(WiffiMetric(var))

        if self._server.callback is not None:
            await self._server.callback(WiffiDevice(moduletype, systeminfo), metrics)


class WiffiTcpServer:
    """Manages TCP server for wiffi devices.

    Opens a single port and listens for incoming TCP connections.
    """

    def __init__(self, port, callback=None):
        """Initialize instance."""
        self.port = port
        self.callback = callback
        self.server = None

    async def start_server(self):
        """Start TCP server on configured port."""
        self.server = await asyncio.start_server(WiffiConnection(self), port=self.port)

    async def close_server(self):
        """Close TCP server."""
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
