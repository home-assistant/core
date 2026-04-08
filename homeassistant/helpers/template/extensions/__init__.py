"""Home Assistant template extensions."""

from .areas import AreaExtension
from .base64 import Base64Extension
from .collection import CollectionExtension
from .crypto import CryptoExtension
from .datetime import DateTimeExtension
from .devices import DeviceExtension
from .floors import FloorExtension
from .functional import FunctionalExtension
from .issues import IssuesExtension
from .labels import LabelExtension
from .math import MathExtension
from .regex import RegexExtension
from .serialization import SerializationExtension
from .string import StringExtension
from .type_cast import TypeCastExtension

__all__ = [
    "AreaExtension",
    "Base64Extension",
    "CollectionExtension",
    "CryptoExtension",
    "DateTimeExtension",
    "DeviceExtension",
    "FloorExtension",
    "FunctionalExtension",
    "IssuesExtension",
    "LabelExtension",
    "MathExtension",
    "RegexExtension",
    "SerializationExtension",
    "StringExtension",
    "TypeCastExtension",
]
