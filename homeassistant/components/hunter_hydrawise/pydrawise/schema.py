# pylint: skip-file
"""GraphQL API schema for pydrawise."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Optional, Union

from apischema.conversions import Conversion
from apischema.metadata import conversion, skip

# The names in this file are from the GraphQL schema and don't always adhere to
# the naming scheme that pylint expects.
# pylint: disable=invalid-name


class StatusCodeEnum(Enum):
    """Response status codes."""

    OK = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class StatusCodeAndSummary:
    """A response status code and a human-readable summary."""

    status: StatusCodeEnum
    summary: str


@dataclass
class LocalizedValueType:
    """A localized value."""

    value: float
    unit: str


@dataclass
class Option:
    """A generic option."""

    value: int
    label: str


@dataclass
class DateTime:
    """A date & time.

    This is only used for serialization and deserialization.
    """

    value: str
    timestamp: int

    @staticmethod
    def from_json(dt: DateTime) -> datetime:
        """Convert a DateTime to a native python type."""
        return datetime.fromtimestamp(dt.timestamp)

    @staticmethod
    def to_json(dt: datetime) -> DateTime:
        """Convert a native datetime to a DateTime GraphQL type."""
        local = dt
        if local.tzinfo is None:
            # Make sure we have a timezone set so strftime outputs a valid string.
            local = local.replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
        return DateTime(
            value=local.strftime("%a, %d %b %y %H:%I:%S %z"),
            timestamp=int(dt.timestamp()),
        )

    @staticmethod
    def conversion() -> conversion:
        """Return a GraphQL conversion for a DateTime."""
        return conversion(
            Conversion(DateTime.from_json, source=DateTime, target=datetime),
            Conversion(DateTime.to_json, source=datetime, target=DateTime),
        )


def _duration_conversion(unit: str) -> conversion:
    assert unit in (
        "days",
        "seconds",
        "microseconds",
        "milliseconds",
        "minutes",
        "hours",
        "weeks",
    )
    return conversion(
        Conversion(lambda d: timedelta(**{unit: d}), source=int, target=timedelta),
        Conversion(lambda d: getattr(d, unit), source=timedelta, target=int),
    )


@dataclass
class BaseZone:
    """Basic zone information."""

    id: int
    controller_id: int
    number: Option
    name: str


@dataclass
class CycleAndSoakSettings:
    """Cycle and soak durations."""

    cycle_duration: timedelta = field(metadata=_duration_conversion("minutes"))
    soak_duration: timedelta = field(metadata=_duration_conversion("minutes"))


@dataclass
class RunTimeGroup:
    """The runtime of a watering program group."""

    id: int
    duration: timedelta = field(metadata=_duration_conversion("minutes"))


@dataclass
class AdvancedProgram:
    """An advanced watering program."""

    advanced_program_id: int
    run_time_group: RunTimeGroup


class AdvancedProgramDayPatternEnum(Enum):
    """A value for an advanced watering program day pattern."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Determine the value for an auto() call."""
        return name

    EVEN = auto()
    ODD = auto()
    MONDAY = auto()
    TUESDAY = auto()
    WEDNESDAY = auto()
    THURSDAY = auto()
    FRIDAY = auto()
    SATURDAY = auto()
    SUNDAY = auto()
    DAYS = auto()


@dataclass
class ProgramStartTime:
    """Start time for a watering program."""

    id: int
    time: str  # e.g. "02:00"
    watering_days: list[AdvancedProgramDayPatternEnum]


@dataclass
class WateringSettings:
    """Generic settings for a watering program."""

    fixed_watering_adjustment: int
    cycle_and_soak_settings: Optional[CycleAndSoakSettings]


@dataclass
class AdvancedWateringSettings(WateringSettings):
    """Advanced watering program settings."""

    advanced_program: Optional[AdvancedProgram]


@dataclass
class StandardProgram:
    """A standard watering program."""

    name: str
    start_times: list[str]


@dataclass
class StandardProgramApplication:
    """A standard watering program."""

    zone: BaseZone
    standard_program: StandardProgram
    run_time_group: RunTimeGroup


@dataclass
class StandardWateringSettings(WateringSettings):
    """Standard watering settings."""

    standard_program_applications: list[StandardProgramApplication]


@dataclass
class RunStatus:
    """Run status."""

    value: int
    label: str


@dataclass
class ScheduledZoneRun:
    """A scheduled zone run."""

    id: str
    start_time: datetime = field(metadata=DateTime.conversion())
    end_time: datetime = field(metadata=DateTime.conversion())
    normal_duration: timedelta = field(metadata=_duration_conversion("minutes"))
    duration: timedelta = field(metadata=_duration_conversion("minutes"))
    remaining_time: timedelta = field(metadata=_duration_conversion("seconds"))
    status: RunStatus


@dataclass
class ScheduledZoneRuns:
    """Scheduled runs for a zone."""

    summary: str
    current_run: Optional[ScheduledZoneRun]
    next_run: Optional[ScheduledZoneRun]
    status: Optional[str]


@dataclass
class PastZoneRuns:
    """Previous zone runs."""

    last_run: Optional[ScheduledZoneRun]
    runs: list[ScheduledZoneRun]


@dataclass
class ZoneStatus:
    """A zone's status."""

    relative_water_balance: int
    suspended_until: Optional[datetime] = field(metadata=DateTime.conversion())


@dataclass
class ZoneSuspension:
    """A zone suspension."""

    id: int
    start_time: datetime = field(metadata=DateTime.conversion())
    end_time: datetime = field(metadata=DateTime.conversion())


@dataclass
class Zone(BaseZone):
    """A watering zone."""

    watering_settings: Union[AdvancedWateringSettings, StandardWateringSettings]
    scheduled_runs: ScheduledZoneRuns
    past_runs: PastZoneRuns
    status: ZoneStatus
    suspensions: list[ZoneSuspension] = field(default_factory=list)


@dataclass
class ControllerFirmware:
    """Information about the controller's firmware."""

    type: str
    version: str


@dataclass
class ControllerModel:
    """Information about a controller model."""

    name: str
    description: str


@dataclass
class ControllerHardware:
    """Information about a controller's hardware."""

    serial_number: str
    version: str
    status: str
    model: ControllerModel
    firmware: list[ControllerFirmware]


@dataclass
class SensorModel:
    """Information about a sensor model."""

    id: int
    name: str
    active: bool
    off_level: int
    off_timer: int
    delay: int
    divisor: float
    flow_rate: float


@dataclass
class SensorStatus:
    """Current status of a sensor."""

    water_flow: Optional[LocalizedValueType]
    active: bool


@dataclass
class SensorFlowSummary:
    """Summary of a sensor's water flow."""

    total_water_volume: LocalizedValueType


@dataclass
class Sensor:
    """A sensor connected to a controller."""

    id: int
    name: str
    model: SensorModel
    status: SensorStatus


@dataclass
class WaterTime:
    """A water time duration."""

    value: timedelta = field(metadata=_duration_conversion("minutes"))


@dataclass
class ControllerStatus:
    """Current status of a controller."""

    summary: str
    online: bool
    actual_water_time: WaterTime
    normal_water_time: WaterTime
    last_contact: Optional[DateTime] = None


@dataclass
class Controller:
    """A Hydrawise controller."""

    id: int
    name: str
    software_version: str
    hardware: ControllerHardware
    last_contact_time: datetime = field(metadata=DateTime.conversion())
    last_action: datetime = field(metadata=DateTime.conversion())
    online: bool
    sensors: list[Sensor]
    zones: list[Zone] = field(default_factory=list, metadata=skip(deserialization=True))
    permitted_program_start_times: list[ProgramStartTime] = field(default_factory=list)
    status: Optional[ControllerStatus] = field(default=None)


@dataclass
class User:
    """A Hydrawise user account."""

    id: int
    customer_id: int
    name: str
    email: str
    controllers: list[Controller] = field(
        default_factory=list, metadata=skip(deserialization=True)
    )


class Query(ABC):
    """GraphQL schema for queries.

    :meta private:
    """

    @staticmethod
    @abstractmethod
    def me() -> User:
        """Return the current user.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def controller(controller_id: int) -> Controller:
        """Return a controller by its unique identifier.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def zone(zone_id: int) -> Zone:
        """Return a zone by its unique identifier.

        :meta private:
        """


class Mutation(ABC):
    """GraphQL schema for mutations.

    :meta private:
    """

    @staticmethod
    @abstractmethod
    def start_zone(
        zone_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
        stack_runs: bool = False,
    ) -> StatusCodeAndSummary:
        """Start a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def stop_zone(zone_id: int) -> StatusCodeAndSummary:
        """Stop a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def suspend_zone(zone_id: int, until: str) -> StatusCodeAndSummary:
        """Suspend a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def resume_zone(zone_id: int) -> StatusCodeAndSummary:
        """Resume a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def start_all_zones(
        controller_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> StatusCodeAndSummary:
        """Start all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def stop_all_zones(controller_id: int) -> StatusCodeAndSummary:
        """Stop all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def suspend_all_zones(controller_id: int, until: str) -> StatusCodeAndSummary:
        """Suspend all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def resume_all_zones(controller_id: int) -> StatusCodeAndSummary:
        """Resume all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def delete_zone_suspension(id: int) -> bool:  # pylint: disable=redefined-builtin
        """Delete a zone suspension.

        :meta private:
        """
