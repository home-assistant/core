"""Entity classes for the Avocent Direct PDU integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AvocentDpduDataUpdateCoordinator


class OutletEntity(CoordinatorEntity[AvocentDpduDataUpdateCoordinator]):
    """Define an Outlet entity."""


class CurrentEntity(CoordinatorEntity[AvocentDpduDataUpdateCoordinator]):
    """Define an current sensor entity."""
