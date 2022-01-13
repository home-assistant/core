"""AVM FRITZ!Box API wrapper."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzLookUpError,
    FritzSecurityError,
    FritzServiceError,
)

from .common import FritzBoxTools

_LOGGER = logging.getLogger(__name__)


class AvmWrapper:
    """Setup AVM wrapper for API calls."""

    def __init__(self, avm_device: FritzBoxTools) -> None:
        """Init wrapper API class."""

        self._avm_device = avm_device

    def _service_call_action(
        self,
        service_name: str,
        service_suffix: str,
        action_name: str,
        **kwargs: Any,
    ) -> dict | None:
        """Return service details."""

        if (
            f"{service_name}{service_suffix}"
            not in self._avm_device.connection.services
        ):
            return None

        try:
            result: dict = self._avm_device.connection.call_action(
                f"{service_name}:{service_suffix}",
                action_name,
                **kwargs,
            )
            return result
        except FritzSecurityError:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
                exc_info=True,
            )
        except (
            FritzActionError,
            FritzActionFailedError,
            FritzServiceError,
            FritzLookUpError,
        ):
            _LOGGER.error(
                "Service/Action Error: cannot execute service %s with action %s",
                service_name,
                action_name,
                exc_info=True,
            )
        except FritzConnectionException:
            _LOGGER.error(
                "Connection Error: Please check the device is properly configured for remote login",
                exc_info=True,
            )
        return None

    async def _async_service_call_action(
        self, service_name: str, service_suffix: str, action_name: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Make call_action async."""

        return await self._avm_device.hass.async_add_executor_job(
            partial(
                self._service_call_action,
                service_name,
                service_suffix,
                action_name,
                **kwargs,
            )
        )

    async def get_wan_dsl_interface_config(self) -> dict[str, Any] | None:
        """Call WANDSLInterfaceConfig service."""

        return await self._async_service_call_action(
            "WANDSLInterfaceConfig",
            "1",
            "GetInfo",
        )
