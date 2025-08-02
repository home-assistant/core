"""Utils for Onkyo."""

from .const import InputSource, ListeningMode


def get_meaning(param: InputSource | ListeningMode) -> str:
    """Get param meaning."""
    return " ··· ".join(param.meanings)
