"""Base entity for Azure DevOps."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AwsDataEC2ServicesCoordinator


class AwsDataEC2RegionEntity(CoordinatorEntity[AwsDataEC2ServicesCoordinator]):
    """Defines an AWS EC2 entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AwsDataEC2ServicesCoordinator,
    ) -> None:
        """Initialize the AWS EC2 entity."""
        super().__init__(coordinator)
