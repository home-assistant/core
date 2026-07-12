"""Constants for the solax integration."""

from importlib.metadata import EntryPoint, entry_points

DOMAIN = "solax"

MANUFACTURER = "SolaX Power"

SOLAX_INVERTER_ENTRY_POINT_GROUP = "solax.inverter"

INVERTER_MODELS: dict[str, EntryPoint] = {
    ep.name: ep for ep in entry_points(group=SOLAX_INVERTER_ENTRY_POINT_GROUP)
}
