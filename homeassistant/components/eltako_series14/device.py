"""Support for Eltako Series 14 devices."""

from dataclasses import dataclass, field
from enum import Enum, auto


class SwitchEntities(Enum):
    """Representation of the different Eltako switch entity types."""

    STANDARD = auto()
    DUMB = auto()


@dataclass
class ModelDefinition:
    """Representation of an Eltako device model."""

    name: str
    switches: set[SwitchEntities] = field(default_factory=set[SwitchEntities])


@dataclass
class GatewayModelDefinition(ModelDefinition):
    """Representation of an Eltako gateway model."""

    is_bus_gw: bool = True
    baud_rate: int = 57600


GATEWAY_MODELS: dict[str, GatewayModelDefinition] = {
    "FAM14": GatewayModelDefinition("FAM14"),
    "FGW14_USB": GatewayModelDefinition("FGW14-USB"),
    "FAM_USB": GatewayModelDefinition("FAM-USB", baud_rate=9600),
}

SWITCH_MODELS: dict[str, ModelDefinition] = {
    "FSR14_2x": ModelDefinition("FSR14-2x", switches={SwitchEntities.STANDARD}),
    "FSR14_4x": ModelDefinition("FSR14-4x", switches={SwitchEntities.STANDARD}),
    "FMS14": ModelDefinition("FMS14", switches={SwitchEntities.DUMB}),
}

MODELS = GATEWAY_MODELS | SWITCH_MODELS
