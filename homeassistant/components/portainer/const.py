"""Constants for the Portainer integration."""

DOMAIN = "portainer"
DEFAULT_NAME = "Portainer"

API_MAX_RETRIES = 3

CONTAINER_STATE_ACTIONS = {
    "start",
    "stop",
    "die",
    "kill",
    "pause",
    "unpause",
    "restart",
    "oom",
    "update",
}

HEALTH_STATUS_VALUES = ("healthy", "unhealthy", "starting")

CONTAINER_STATE_EVENT_TYPES: tuple[str, ...] = tuple(
    sorted(CONTAINER_STATE_ACTIONS)
) + tuple(f"health_status_{value}" for value in HEALTH_STATUS_VALUES)
