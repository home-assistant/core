"""File contains custom exceptions used in Papouch library."""


class DeviceError(Exception):
    """Base error for every kind of devices."""


class DeviceConnectionError(DeviceError):
    """Connection error."""


class DeviceAuthError(DeviceError):
    """Authorization error."""


class DeviceResponseError(DeviceError):
    """Response error."""


class DeviceLogicError(DeviceError):
    """Logic error."""


class DeviceParseError(DeviceError):
    """Parse XML error."""
