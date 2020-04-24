"""Classes for Natural Resources Wales flood warnings."""


class NaturalResourcesWalesLiveFloodWarningsComponent:
    """Natural Resources Wales component to wrap live flood warnings sensors and data."""

    def __init__(self, river_levels_key, language, interval, monitored):
        """Initialize wrapper."""
