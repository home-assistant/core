"""Qbus MQTT data classes."""


class QbusMqttOutput:
    """MQTT representation of a Qbus output."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict

    @property
    def id(self) -> str:
        """Return the id."""
        return self._dict.get("id") or ""

    @property
    def type(self) -> str:
        """Return the type."""
        return self._dict.get("type") or ""

    @property
    def name(self) -> str:
        """Return the name."""
        return self._dict.get("name") or ""

    @property
    def ref_id(self) -> str:
        """Return the ref id."""
        return self._dict.get("refId") or ""

    @property
    def properties(self) -> dict:
        """Return the properties."""
        return self._dict.get("properties") or {}

    @property
    def actions(self) -> dict:
        """Return the actions."""
        return self._dict.get("actions") or {}


class QbusMqttDevice:
    """MQTT representation of a Qbus controller."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict
        self._outputs: list[QbusMqttOutput] = []
        self._connection_state: bool

    @property
    def id(self) -> str:
        """Return the id."""
        return self._dict.get("id") or ""

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        return self._dict.get("serialNr") or ""

    @property
    def firmware_version(self) -> str:
        """Return the firmware version."""
        return self._dict.get("version") or ""

    @property
    def mac(self) -> str:
        """Return the mac address."""
        return self._dict.get("mac") or ""

    @property
    def outputs(self) -> list[QbusMqttOutput]:
        """Return the outputs."""

        outputs: list[QbusMqttOutput] = []

        if self._dict.get("functionBlocks"):
            outputs = [QbusMqttOutput(x) for x in self._dict["functionBlocks"]]

        self._outputs = outputs
        return self._outputs


class QbusMqttConfig:
    """MQTT representation of the entire Qbus configuration."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict
        self._devices: list[QbusMqttDevice] = []

    @property
    def devices(self) -> list[QbusMqttDevice]:
        """Return the devices."""

        devices: list[QbusMqttDevice] = []

        if self._dict.get("devices"):
            devices = [QbusMqttDevice(x) for x in self._dict["devices"]]

        self._devices = devices

        return self._devices

    def get_device(self, serial: str) -> QbusMqttDevice | None:
        """Get the device by serial number."""
        return next((x for x in self.devices if x.serial_number == serial), None)


class QbusMqttControllerStateProperties:
    """MQTT representation a Qbus controller its state properties."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict

    @property
    def connectable(self) -> bool | None:
        """Return True if the controller is connectable."""
        return self._dict.get("connectable", None)

    @property
    def connected(self) -> bool | None:
        """Return True if the controller is connected."""
        return self._dict.get("connected", None)


class QbusMqttControllerState:
    """MQTT representation a Qbus controller state."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict
        self._properties: QbusMqttControllerStateProperties | None = None

    @property
    def id(self) -> str | None:
        """Return the id."""
        return self._dict.get("id")

    @property
    def properties(self) -> QbusMqttControllerStateProperties | None:
        """Return the properties."""

        if self._properties is not None:
            return self._properties

        properties: QbusMqttControllerStateProperties | None = None

        if self._dict.get("properties"):
            properties = QbusMqttControllerStateProperties(self._dict["properties"])

        self._properties = properties

        return self._properties


class QbusMqttOutputState:
    """MQTT representation a Qbus output state."""

    def __init__(self, dict: dict) -> None:
        """Initialize based on a json loaded dictionary."""
        self._dict = dict

    @property
    def id(self) -> str:
        """Return the id."""
        return self._dict.get("id") or ""

    @property
    def type(self) -> str:
        """Return the type."""
        return self._dict.get("type") or ""

    @property
    def properties(self) -> dict | None:
        """Return the properties."""
        return self._dict.get("properties")
