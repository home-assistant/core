"""Constants for the solax integration."""

from importlib.metadata import entry_points

from solax.inverter import Inverter

DOMAIN = "solax"

MANUFACTURER = "SolaX Power"

SOLAX_INVERTER_ENTRY_POINT_GROUP = "solax.inverter"

INVERTER_MODELS: dict[str, type[Inverter]] = {
    ep.name: ep.load() for ep in entry_points(group=SOLAX_INVERTER_ENTRY_POINT_GROUP)
}
