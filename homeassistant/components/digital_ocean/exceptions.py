"""Store all custom exceptions for this integration."""


from homeassistant.exceptions import HomeAssistantError


class DomainRecordsNotFound(HomeAssistantError):
    """Error used to indicate no domain records are found in Digital Ocean."""


class UpdateThrottled(HomeAssistantError):
    """Error used to indicate too frequent updates."""


class DomainRecordAlreadySet(HomeAssistantError):
    """Exception used to indicate update was skipped."""
