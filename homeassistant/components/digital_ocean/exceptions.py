"""Store all custom exceptions for this integration."""


from homeassistant.exceptions import ServiceValidationError


class DomainRecordsNotFound(ServiceValidationError):
    """Error used to indicate no domain records are found in Digital Ocean."""


class UpdateThrottled(ServiceValidationError):
    """Error used to indicate too frequent updates."""


class DomainRecordAlreadySet(ServiceValidationError):
    """Exception used to indicate update was skipped."""
