"""Helpers for LaMetric."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from demetriek import LaMetricConnectionError, LaMetricError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service

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
    config_entry: LaMetricConfigEntry
    _, config_entry = service.async_get_device_and_config_entry(hass, DOMAIN, device_id)
    return config_entry.runtime_data
