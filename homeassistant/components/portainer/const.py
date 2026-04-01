"""Constants for the Portainer integration."""

from enum import IntEnum, StrEnum

DOMAIN = "portainer"
DEFAULT_NAME = "Portainer"

API_MAX_RETRIES = 3


class EndpointStatus(IntEnum):
    """Portainer endpoint status."""

    UP = 1
    DOWN = 2


class ContainerState(StrEnum):
    """Portainer container state."""

    RUNNING = "running"


class StackStatus(IntEnum):
    """Portainer stack status."""

    ACTIVE = 1
    INACTIVE = 2


class StackType(IntEnum):
    """Portainer stack type."""

    SWARM = 1
    COMPOSE = 2
    KUBERNETES = 3
