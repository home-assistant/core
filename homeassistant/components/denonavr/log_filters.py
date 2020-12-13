"""Log filters for DenonAVR."""
import logging


class SilenceFilter(logging.Filter):
    """Silence logging."""

    def filter(self, record):
        """Silence logging."""
        return False


class TimeoutFilter(logging.Filter):
    """Check for API failure and handle."""

    def __init__(self, ref=None):
        """Init reference to the DenonDevice object."""
        self.ref = ref
        super().__init__()

    def filter(self, record):
        """Check for API failure and handle."""
        if record.getMessage().startswith("Missing status information from XML of"):
            self.ref.handle_api_status(False)
        return True
