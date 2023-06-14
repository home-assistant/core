"""Provides an interface for feed data provided by EmonCMS."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


class Feed:
    """Stores the data provided by an EmonCMS server about a given feed."""

    _id: int
    """The id of the feed"""
    _userid: int
    """The id of the user that created the feed"""
    _name: str
    """The name of the feed"""
    _tag: str
    """The tag of the feed"""
    _public: bool
    """Whether the feed is public"""
    _size: str
    """The calculated size of the feed"""
    _engine: int
    """The engine used for calculating the feed"""
    _unit: str
    """The unit set for the feed"""

    _attr_device_class: SensorDeviceClass | None = None
    """Stores the device class that should be used with this feed"""
    _attr_state_class: str | None = None
    """Stores the state class that should be used with this feed"""

    raw_value: str | None = None
    """Stores the raw value read from the EmonCMS installation"""
    last_update: datetime | None = None
    """Stores the time at which raw_value was received in the target server"""

    def __init__(
        self,
        feed_id: int,
        userid: int,
        name: str,
        tag: str,
        public: bool,
        size: str,
        engine: int,
        unit: str,
    ) -> None:
        """Initialize the Feed class with data obtained from the Feed endpoint of EmonCMS."""

        self._id = feed_id
        self._userid = userid
        self._name = name
        self._tag = tag
        self._public = public
        self._size = size
        self._engine = engine
        self._unit = unit

        if unit in ("kWh", "Wh"):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "W":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "VA":
            self._attr_device_class = SensorDeviceClass.APPARENT_POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit in ("°C", "°F", "K"):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "hPa":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "%" and "SOC" in name.upper():
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def id(self) -> int:
        """Returns the id of the feed."""

        return self._id

    @property
    def name(self) -> str:
        """Returns the name of the feed."""

        return self._name

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Returns the device class to be used with the feed."""

        return self._attr_device_class

    @property
    def state_class(self) -> str | None:
        """Returns the state class to be used with the feed."""

        return self._attr_state_class

    @property
    def unit(self) -> str:
        """Returns the unit associated with the feed type."""

        return self._unit

    @property
    def processed_value(self) -> str | float | None:
        """Converts the stored raw_value into a usable value. This means checking its nullity, and converting to float, depending on the device class."""

        if self.raw_value is None or self.raw_value == "null":
            return None

        if self._attr_state_class == SensorStateClass.MEASUREMENT:
            return float(self.raw_value)

        return self.raw_value
