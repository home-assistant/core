"""Runtime models for the WiiM integration."""

from dataclasses import dataclass, field

from wiim.controller import WiimController


@dataclass
class WiimData:
    """Runtime data for the WiiM integration shared across platforms."""

    controller: WiimController
    entity_id_to_udn_map: dict[str, str] = field(default_factory=dict)
