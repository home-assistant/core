"""Code for parent class for all Livisi devices."""


class Device:
    """Represents the parent class for Livisi devices."""

    @property
    def capability_id(self) -> str:
        """Return the capability id of the device."""

    @property
    def available(self):
        """Return if device is available."""

    def update_states(self, states) -> None:
        """Update the devices states."""

    def update_reachability(self, is_reachable: bool) -> None:
        """Update the devices rechability."""
