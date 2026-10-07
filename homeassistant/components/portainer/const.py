"""Constants for the Portainer integration."""

from pyportainer import DockerContainerState

DOMAIN = "portainer"
DEFAULT_NAME = "Portainer"

API_MAX_RETRIES = 3

CONTAINER_STATE_ACTIONS: dict[str, DockerContainerState | None] = {
    "start": DockerContainerState.RUNNING,
    "stop": DockerContainerState.EXITED,
    "die": DockerContainerState.EXITED,
    "kill": None,
    "pause": DockerContainerState.PAUSED,
    "unpause": DockerContainerState.RUNNING,
    "restart": DockerContainerState.RUNNING,
    "oom": None,
    "update": None,
}

HEALTH_STATUS_VALUES = ("healthy", "unhealthy", "starting")

CONTAINER_STATE_EVENT_TYPES: tuple[str, ...] = tuple(
    sorted(CONTAINER_STATE_ACTIONS)
) + tuple(f"health_status_{value}" for value in HEALTH_STATUS_VALUES)
