"""Helpers for LaMetric."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from demetriek import LaMetricConnectionError, LaMetricError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity


def lametric_exception_handler[_LaMetricEntityT: LaMetricEntity, **_P](
    func: Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate LaMetric calls to handle LaMetric exceptions.

    A decorator that wraps the passed in function, catches LaMetric errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(
        self: _LaMetricEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except LaMetricConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                "Error communicating with the LaMetric device"
            ) from error

        except LaMetricError as error:
            raise HomeAssistantError(
                "Invalid response from the LaMetric device"
            ) from error

    return handler


@callback
def async_get_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> LaMetricDataUpdateCoordinator:
    """Get the LaMetric coordinator for this device ID."""
    config_entry: LaMetricConfigEntry | None
    device, config_entry = dr.async_get_device_and_config_entry_for_domain(
        hass, device_id, domain=DOMAIN
    )

    if device is None:
        raise ValueError(f"Unknown LaMetric device ID: {device_id}")

    if config_entry is None or config_entry.state is not ConfigEntryState.LOADED:
        raise ValueError(f"No coordinator for device ID: {device_id}")

    return config_entry.runtime_data
