"""A BroadcastMemory packet."""

import logging
from typing import Any

from .json import Jsonable
from .packet import Packet

_LOGGER = logging.getLogger(__name__)


class SystemPropertyList(Jsonable):
    """Properties for the LC7001 system."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__()

        self.AddASceneController: bool | None = kwargs.get("AddASceneController")
        self.AddALight: bool | None = kwargs.get("AddALight")
        self.TimeZone: int | None = kwargs.get("TimeZone")
        self.DaylightSavingTime: bool | None = kwargs.get("DaylightSavingTime")
        self.LocationInfo: str | None = kwargs.get("LocationInfo")
        self.Location: dict | None = kwargs.get("Location")


class ReportSystemProperties(Packet):
    """A SystemProperties packet."""

    _service_name = "ReportSystemProperties"

    def __init__(
        self,
        PropertyList: SystemPropertyList | dict | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize."""
        super().__init__(**kwargs)

        self.PropertyList = (
            SystemPropertyList(**PropertyList)
            if isinstance(PropertyList, dict)
            else SystemPropertyList(**vars(PropertyList))
            if isinstance(PropertyList, SystemPropertyList)
            else None
        )


class SystemInfo(Packet):
    """Represents a SystemInfo packet from LC7001."""

    _service_name = "SystemInfo"

    def __init__(
        self,
        Model: str | None = None,
        FirmwareVersion: str | None = None,
        FirmwareDate: str | None = None,
        FirmwareBranch: str | None = None,
        MACAddress: str | None = None,
        UpdateState: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize."""
        super().__init__(**kwargs)

        self.Model = Model
        self.FirmwareVersion = FirmwareVersion
        self.FirmwareDate = FirmwareDate
        self.FirmwareBranch = FirmwareBranch
        self.MACAddress = MACAddress
        self.UpdateState = UpdateState
