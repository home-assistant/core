"""This file contains classes that define Papouch devices."""

import defusedxml.ElementTree as ET

from ..APIClient import PapouchApiClient
from .base import PapouchDevice


class Quido(PapouchDevice):
    """Represents devices of Quido family."""

    def __init__(self, api_client: PapouchApiClient) -> None:
        # TODO:look at it, it is needed in creating entities
        """Constructor for Quido device."""
        self.name = "Papouch Quido"
        self.manufacturer = "Papouch s.r.o."
        self.api_client = api_client

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

    async def connect_all_coils(self) -> None:
        """Command for connecting all the coils."""
        await self.api_client.send_command("S")

    async def disconnect_all_coils(self) -> None:
        """Command for disconnecting all the coils."""
        await self.api_client.send_command("R")

    # TODO: clearing and decreasing counter is not possible in Qudio ETH 3/0B add it with extra logic
    async def reset_all_counters(self) -> None:
        """Command for resetting all the counters."""
        await self.api_client.send_command("C")

    async def decrease_value_counter(self, item_id: str, value: int) -> None:
        """Command for decreasing specific counter."""
        return await self.api_client.send_command("c", item_id, value)

    async def turn_on_coil(self, item_id: str) -> None:
        """Command for turning on the coil by its id."""
        return await self.api_client.send_command("s", item_id)

    async def turn_off_coil(self, item_id: str) -> None:
        """Command for turning off the coil by its id."""
        return await self.api_client.send_command("r", item_id)
