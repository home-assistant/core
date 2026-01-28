"""Home Assistant template extensions."""

from .areas import AreaExtension
from .base64 import Base64Extension
from .collection import CollectionExtension
from .crypto import CryptoExtension
from .datetime import DateTimeExtension
from .devices import DeviceExtension
from .floors import FloorExtension
from .issues import IssuesExtension
from .labels import LabelExtension
from .math import MathExtension
from .regex import RegexExtension
from .string import StringExtension

__all__ = [
    "AreaExtension",
    "Base64Extension",
    "CollectionExtension",
    "CryptoExtension",
    "DateTimeExtension",
    "DeviceExtension",
    "FloorExtension",
    "IssuesExtension",
    "LabelExtension",
    "MathExtension",
    "RegexExtension",
    "StringExtension",
]
