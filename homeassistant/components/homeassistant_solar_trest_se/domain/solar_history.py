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
        self.serial_number = data.get("serial_number")
        self.battery_discharge = data.get("battery_discharge")
        self.battery_charge = data.get("battery_charge")
        self.battery_capacity = data.get("battery_capacity")
        self.battery_stored_power = data.get("battery_stored_power")
        self.total_load_active_power = data.get("total_load_active_power")
        self.realtime_solar = data.get("realtime_solar")
        self.timestamp = data.get("timestamp")
        self.solar_profile = data.get("solar_profile")
        self.daily_yeild = data.get("daily_yeild")
