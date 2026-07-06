"""Models for Ruuvi Gateway integration."""

import dataclasses

from .bluetooth import RuuviGatewayScanner
from .coordinator import RuuviGatewayUpdateCoordinator


@dataclasses.dataclass(frozen=True)
class RuuviGatewayRuntimeData:
    """Runtime data for Ruuvi Gateway integration."""

    update_coordinator: RuuviGatewayUpdateCoordinator
    scanner: RuuviGatewayScanner
