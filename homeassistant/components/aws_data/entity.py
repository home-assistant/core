"""Base entity for AWS Data."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AwsDataRegionCoordinator


class AwsDataEntity(CoordinatorEntity[AwsDataRegionCoordinator]):
    """Defines an AWS EC2 entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AwsDataRegionCoordinator,
    ) -> None:
        """Initialize the AWS EC2 entity."""
        super().__init__(coordinator)
