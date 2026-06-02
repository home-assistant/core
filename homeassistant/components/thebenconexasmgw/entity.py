"""Base Entity for the Theben Conexa Smartmeter gateway integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SmgwSensorCoordinator


class ConexaSMGWEntity(CoordinatorEntity[SmgwSensorCoordinator]):
    """Defines a base Theben Conexa Smartmeter gateway entity."""

    def __init__(self, coordinator: SmgwSensorCoordinator) -> None:
        """Initialize the Base entity."""
        super().__init__(coordinator)
        # TODO: What should go here? pylint: disable=fixme
