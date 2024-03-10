"""Class file for the entity SolarHistory."""


class SolarHistory:
    """The entity for SolarHistory."""

    id: int | None
    serial_number: str | None
    battery_discharge: str | None
    battery_charge: str | None
    battery_capacity: str | None
    battery_stored_power: str | None
    total_load_active_power: str | None
    realtime_solar: str | None
    timestamp: str | None
    solar_profile: str | None
    daily_yeild: str | None

    def __init__(self, data) -> None:  # noqa: D107
        self.id = data.get("id")
        self.serial_number = data.get("serialNumber")
        self.battery_discharge = data.get("batteryDischarge")
        self.battery_charge = data.get("batteryCharge")
        self.battery_capacity = data.get("batteryCapacity")
        self.battery_stored_power = data.get("batteryStoredPower")
        self.total_load_active_power = data.get("totalLoadActivePower")
        self.realtime_solar = data.get("realtimeSolar")
        self.timestamp = data.get("timestamp")
        self.solar_profile = data.get("solarProfile")
        self.daily_yeild = data.get("dailyYeild")

    def to_dict(self):
        """Convert SolarHistory object to a dictionary."""
        return {
            "id": self.id,
            "serial_number": self.serial_number,
            "battery_discharge": self.battery_discharge,
            "battery_charge": self.battery_charge,
            "battery_capacity": self.battery_capacity,
            "battery_stored_power": self.battery_stored_power,
            "total_load_active_power": self.total_load_active_power,
            "realtime_solar": self.realtime_solar,
            "timestamp": self.timestamp,
            "solar_profile": self.solar_profile,
            "daily_yeild": self.daily_yeild,
        }
