"""This file contains classes that define Papouch devices.

Every device has parse method that parses its own XML.

"""

from abc import ABC, abstractmethod

import defusedxml.ElementTree as ET


class PapouchDevice(ABC):
    """Abstract class for Papouch devices."""

    @abstractmethod
    def parse_xml(self, xml_data: str) -> dict:
        """Abstract method for parsing XML."""


class Quido(PapouchDevice):
    """Represents devices of Quido family."""

    def parse_xml(self, xml_data: str) -> dict:
        """Defines parser method for Quido family."""
        root = ET.fromstring(xml_data)
        parsed_data = {"temp": {}, "din": {}, "dout": {}, "din_cnt": {}}

        for element in root:
            item_id = element.attrib.get("id")

            if element.tag == "temp":
                val_str = element.attrib.get("val", "0")
                parsed_data["temp"][item_id] = float(val_str)

            elif element.tag == "dout":
                val_str = element.attrib.get("val", "0")
                parsed_data["dout"][item_id] = int(val_str)

            elif element.tag == "din":
                parsed_data["din"][item_id] = int(element.attrib.get("val", "0"))
                parsed_data["din_cnt"][item_id] = int(element.attrib.get("cnt", "0"))

        return parsed_data
