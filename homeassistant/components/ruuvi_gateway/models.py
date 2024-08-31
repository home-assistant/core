"""Models for Ruuvi Gateway integration."""
from __future__ import annotations

import dataclasses

from .bluetooth import RuuviGatewayScanner
from .coordinator import RuuviGatewayUpdateCoordinator


@dataclasses.dataclass(frozen=True)
class RuuviGatewayRuntimeData:
    """Runtime data for Ruuvi Gateway integration."""

    update_coordinator: RuuviGatewayUpdateCoordinator
    scanner: RuuviGatewayScanner
