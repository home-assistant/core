"""Samsung SyncThru exceptions."""

from homeassistant.exceptions import HomeAssistantError


class SyncThruNotSupported(HomeAssistantError):
    """Error to indicate SyncThru is not supported."""
