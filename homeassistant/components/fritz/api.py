"""AVM FRITZ!Box connectivity sensor."""
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


class AvmApi:
    """Setup AVM api calls."""

    def __init__(self, avm_device: FritzBoxTools) -> None:
        """Init API class."""

        self._avm_device = avm_device

    def _service_call_action(
        self,
        service_name: str,
        service_suffix: str | None,
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
            return self._avm_device.connection.call_action(  # type: ignore[no-any-return]
                f"{service_name}:{service_suffix}",
                action_name,
                **kwargs,
            )
        except FritzSecurityError:
            _LOGGER.error(
                "Authorization Error: Please check the provided credentials and verify that you can log into the web interface",
                exc_info=True,
            )
            return None
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
            return None
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

    async def wan_dsl_interface_config(self) -> dict[str, Any] | None:
        """Call WANDSLInterfaceConfig service."""

        return await self._async_service_call_action(
            "WANDSLInterfaceConfig",
            "1",
            "GetInfo",
        )
