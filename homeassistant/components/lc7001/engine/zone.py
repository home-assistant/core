"""The Zone (light) packet and its related classes."""

from enum import StrEnum, auto
import logging
from typing import Any

from .packet import Packet

_LOGGER = logging.getLogger(__name__)


class ZoneDeviceType(StrEnum):
    """Enumeration of possible zone types."""

    Switch = auto()
    Dimmer = auto()


class ZonePropertyList:
    """The properties of a zone."""

    def __init__(
        self,
        PropertyList: Any | None = None,
        Name: str | None = None,
        DeviceType: ZoneDeviceType | None = None,
        Power: bool | None = None,
        PowerLevel: int | None = None,
    ) -> None:
        """Initialize the properties of a zone."""
        self.Name: str | None = None
        self.DeviceType: ZoneDeviceType | None = None
        self.Power: bool | None = None
        self.PowerLevel: int | None = None

        if PropertyList and isinstance(PropertyList, dict) is False:
            PropertyList = vars(PropertyList)

        if PropertyList and isinstance(PropertyList, dict):
            self.Name = PropertyList.get("Name")
            self.DeviceType = PropertyList.get("DeviceType")
            self.Power = PropertyList.get("Power")
            self.PowerLevel = PropertyList.get("PowerLevel")
        else:
            self.Name = Name
            self.DeviceType = DeviceType
            self.Power = Power
            self.PowerLevel = PowerLevel

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of the properties."""
        selfDict: dict[str, Any] = {}

        if self.Name is not None:
            selfDict["Name"] = self.Name

        if self.DeviceType is not None:
            selfDict["DeviceType"] = self.DeviceType

        if self.Power is not None:
            selfDict["Power"] = self.Power

        if self.PowerLevel is not None:
            selfDict["PowerLevel"] = self.PowerLevel

        return selfDict

    def applyChanges(self, changes: "ZonePropertyList") -> None:
        """Update the attributes."""
        self.__dict__.update(changes.asDict())


class Zone:
    """A zone packet from the LC7001."""

    def __init__(
        self,
        ZID: int | None = None,
        PropertyList: ZonePropertyList | dict | None = None,
    ) -> None:
        """Initialize a zone packet."""
        self.ZID = ZID
        self.PropertyList = ZonePropertyList(PropertyList)

    def updateProperties(self, changes: ZonePropertyList) -> None:
        """Update the properties of a zone."""
        if self.PropertyList:
            self.PropertyList.applyChanges(changes)

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of the zone."""
        selfDict: dict[str, Any] = {}

        if self.ZID is not None:
            selfDict["ZID"] = self.ZID

        if self.PropertyList is not None:
            selfDict["PropertyList"] = self.PropertyList

        return selfDict


class ListZones(Packet):
    """The ListZones packet from the LC7001."""

    def __init__(
        self,
        ID: int | None = None,
        ZoneList: list[Zone | dict] | None = None,
        Service: str | None = "ListZones",
        **kwargs: Any,
    ) -> None:
        """Initialize a ListZones packet."""
        super().__init__(ID=ID, Service=Service or "ListZones", **kwargs)

        self.ZoneList: list[Zone] = []

        if ZoneList is not None:
            for zone in ZoneList:
                if isinstance(zone, dict):
                    self.ZoneList.append(Zone(ZID=zone["ZID"]))
                elif isinstance(zone, Zone):
                    self.ZoneList.append(
                        Zone(
                            ZID=zone.ZID,
                            PropertyList=ZonePropertyList(zone.PropertyList),
                        )
                    )

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of the packet."""
        selfDict = super().asDict()

        if self.ZoneList is not None:
            selfDict["ZoneList"] = [zone.asDict() for zone in self.ZoneList]

        return selfDict


class ReportZoneProperties(Packet):
    """A ReportZoneProperties packet from the LC7001."""

    def __init__(
        self,
        Service: str | None = None,
        ZID: int | None = None,
        PropertyList: ZonePropertyList | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a ReportZoneProperties packet."""
        super().__init__(Service=Service or "ReportZoneProperties", **kwargs)

        self.ZID = ZID
        self.PropertyList = ZonePropertyList(PropertyList=PropertyList)

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of the packet."""
        selfDict = super().asDict()

        if self.ZID is not None:
            selfDict["ZID"] = self.ZID

        if self.PropertyList is not None:
            selfDict["PropertyList"] = self.PropertyList.asDict()

        return selfDict


class SetZoneProperties(Packet):
    """A SetZoneProperties from LC7001."""

    def __init__(
        self,
        Service: str | None = None,
        ZID: int | None = None,
        PropertyList: ZonePropertyList | dict | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a SetZoneProperties packet."""
        super().__init__(Service=Service or "SetZoneProperties", **kwargs)
        self.ZID = ZID
        self.PropertyList = ZonePropertyList(PropertyList=PropertyList)

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of the packet."""
        selfDict = super().asDict()

        if self.ZID is not None:
            selfDict["ZID"] = self.ZID

        if self.PropertyList is not None:
            selfDict["PropertyList"] = self.PropertyList.asDict()

        return selfDict
