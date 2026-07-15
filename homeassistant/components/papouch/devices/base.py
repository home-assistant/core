"""This file contains base classes that define Papouch devices."""

from abc import ABC, abstractmethod


class PapouchDevice(ABC):
    """Abstract class for Papouch devices."""

    name: str = ""
    manufacturer: str = ""
    device_identifiers: dict = {()}

    @abstractmethod
    def parse_xml(self, xml_data: str) -> dict:
        """Abstract method for parsing XML."""
