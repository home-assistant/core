"""Shared coordinator entity for iZone."""

from collections.abc import Awaitable
from typing import override

import pizone

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IZoneCoordinator


class IZoneCoordinatorEntity(CoordinatorEntity[IZoneCoordinator]):
    """Coordinator entity with soft-fault availability and command helper."""

    @property
    def controller(self) -> pizone.Controller:
        """Return the pizone controller owned by the entry coordinator."""
        return self.coordinator.controller

    @property
    @override
    def available(self) -> bool:
        """Return True when the last refresh succeeded and the ASH is reachable."""
        return super().available and self.controller.connected

    async def _async_run_and_update(self, coro: Awaitable[None]) -> None:
        """Run a controller/zone command and push local state to the coordinator.

        Rejected commands stay available and raise HomeAssistantError. Transport
        failures mark the coordinator unavailable and also raise HomeAssistantError
        so multi-step service calls stop. A successful command would clear that
        failed flag via async_set_updated_data, but service calls skip unavailable
        entities, so recovery in practice is a later successful coordinator refresh.
        """
        try:
            await coro
        except pizone.ControllerCommandError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={
                    "uid": self.controller.device_uid,
                    "error": str(ex),
                },
            ) from ex
        except ConnectionError as ex:
            self.coordinator.async_set_update_error(ex)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_connect",
                translation_placeholders={"uid": self.controller.device_uid},
            ) from ex
        else:
            self.coordinator.async_set_updated_data(self.controller)
