"""The Zone (light) packet and its related classes."""

from enum import StrEnum, auto
import logging
from typing import Any

from .json import Jsonable
from .packet import Packet

_LOGGER = logging.getLogger(__name__)


class ZoneDeviceType(StrEnum):
    """Enumeration of possible zone types."""

    Switch = auto()
    Dimmer = auto()


class ZonePropertyList(Jsonable):
    """The properties of a zone."""

    def __init__(
        self,
        Name: str | None = None,
        DeviceType: ZoneDeviceType | None = None,
        Power: bool | None = None,
        PowerLevel: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the properties of a zone."""
        super().__init__()
        self.Name = Name
        self.DeviceType = DeviceType
        self.Power = Power
        self.PowerLevel = PowerLevel

    def applyChanges(self, changes: object | dict) -> None:
        """Update the attributes."""
        if isinstance(changes, dict):
            self.__dict__.update(changes)
        else:
            self.__dict__.update(vars(changes))


class Zone(Jsonable):
    """A zone packet from the LC7001."""

    def __init__(
        self,
        ZID: int | None = None,
        PropertyList: ZonePropertyList | dict | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a zone packet."""
        super().__init__(**kwargs)
        self.ZID = ZID
        self.PropertyList = (
            ZonePropertyList(**PropertyList)
            if isinstance(PropertyList, dict)
            else ZonePropertyList(**vars(PropertyList))
            if isinstance(PropertyList, ZonePropertyList)
            else None
        )

    def updateProperties(self, changes: ZonePropertyList) -> None:
        """Update the properties of a zone."""
        if self.PropertyList:
            self.PropertyList.applyChanges(changes)


class ListZones(Packet):
    """The ListZones packet from the LC7001."""

    _service_name = "ListZones"

    def __init__(
        self,
        ZoneList: list[Zone] | list[dict] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a ListZones packet."""
        super().__init__(**kwargs)

        self.ZoneList: list[Zone] | None = (
            [
                Zone(**zone)
                if isinstance(zone, dict)
                else Zone(**vars(zone))
                if isinstance(zone, Zone)
                else {}
                for zone in ZoneList
            ]
            if isinstance(ZoneList, list)
            else None
        )


class ReportZoneProperties(Packet):
    """A ReportZoneProperties packet from the LC7001."""

    _service_name = "ReportZoneProperties"

    def __init__(
        self,
        ZID: int | None = None,
        PropertyList: ZonePropertyList | dict | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a ReportZoneProperties packet."""
        super().__init__(**kwargs)
        self.ZID = ZID
        self.PropertyList = (
            ZonePropertyList(**vars(PropertyList))
            if isinstance(PropertyList, ZonePropertyList)
            else ZonePropertyList(**PropertyList)
            if isinstance(PropertyList, dict)
            else None
        )


class SetZoneProperties(ReportZoneProperties):
    """A SetZoneProperties packet from LC7001."""

    _service_name = "SetZoneProperties"
