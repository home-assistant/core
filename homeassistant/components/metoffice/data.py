"""Common Met Office Data class used by both sensor and entity."""


class MetOfficeData:
    """Data structure for MetOffice weather and forecast."""

    def __init__(self, now, forecast, site):
        """Initialize the data object."""
        self.now = now
        self.forecast = forecast
        self.site = site
