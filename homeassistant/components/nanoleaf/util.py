"""Nanoleaf integration util."""
from pynanoleaf.pynanoleaf import Nanoleaf


def pynanoleaf_get_info(nanoleaf_light: Nanoleaf) -> dict:
    """Get Nanoleaf light info."""
    return nanoleaf_light.info
