"""Classes for Natural Resources Wales flood risk forecast."""


class NaturalResourcesWalesFloodRiskForecastComponent:
    """Natural Resources Wales component to wrap flood risk forecast sensors and data."""

    def __init__(self, river_levels_key, language, interval, monitored):
        """Initialize wrapper."""
