from enum import Enum
from frisquet_connect.domains.model_base import ModelBase


class DayOfWeek(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class ZoneScheduler(ModelBase):
    jour: int

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    @property
    def day_of_week(self) -> DayOfWeek:
        return DayOfWeek(self.jour)
