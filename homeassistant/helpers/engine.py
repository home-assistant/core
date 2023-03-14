"""Base class for Home Assistant engines."""


class Engine:
    """Base class for Home Assistant engines."""

    async def async_internal_added_to_hass(self) -> None:
        """Run when service about to be added to hass.

        Not to be extended by integrations.
        """

    async def async_added_to_hass(self) -> None:
        """Run when service about to be added to hass.

        Not to be extended by integrations.
        """

    async def async_internal_will_remove_from_hass(self) -> None:
        """Prepare to remove the service from Home Assistant.

        Not to be extended by integrations.
        """

    async def async_will_remove_from_hass(self) -> None:
        """Prepare to remove the service from Home Assistant."""
