"""Home Assistant template extensions."""

from .areas import AreaExtension
from .base64 import Base64Extension
from .collection import CollectionExtension
from .crypto import CryptoExtension
from .devices import DeviceExtension
from .floors import FloorExtension
from .labels import LabelExtension
from .math import MathExtension
from .regex import RegexExtension
from .string import StringExtension

__all__ = [
    "AreaExtension",
    "Base64Extension",
    "CollectionExtension",
    "CryptoExtension",
    "DeviceExtension",
    "FloorExtension",
    "LabelExtension",
    "MathExtension",
    "RegexExtension",
    "StringExtension",
]
