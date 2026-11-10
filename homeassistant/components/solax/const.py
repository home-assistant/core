"""Constants for the solax integration."""

from importlib.metadata import EntryPoint, entry_points

from solax.inverter import Inverter

DOMAIN = "solax"

MANUFACTURER = "SolaX Power"

SOLAX_INVERTER_ENTRY_POINT_GROUP = "solax.inverter"

INVERTER_MODELS: dict[str, EntryPoint] = {
    ep.name: ep for ep in entry_points(group=SOLAX_INVERTER_ENTRY_POINT_GROUP)
}


def model_name_for_inverter(inverter: Inverter) -> str:
    """Return the INVERTER_MODELS key matching a discovered inverter instance."""
    return next(
        name
        for name, entry_point in INVERTER_MODELS.items()
        if isinstance(inverter, entry_point.load())
    )
