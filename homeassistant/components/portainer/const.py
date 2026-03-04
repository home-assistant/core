"""Constants for the Portainer integration."""

DOMAIN = "portainer"
DEFAULT_NAME = "Portainer"


class EndpointStatus:
    """Portainer endpoint status."""

    UP = 1
    DOWN = 2


class ContainerState:
    """Portainer container state."""

    RUNNING = "running"


class StackStatus:
    """Portainer stack status."""

    ACTIVE = 1
    INACTIVE = 2


class StackType:
    """Portainer stack type."""

    SWARM = 1
    COMPOSE = 2
    KUBERNETES = 3
