"""requesting and decode Solvis Remote Data.

Solvis remote (SC2) provides xml data when sc2_val.xml is requested from the solvis remote network interface.
the returned payload data has a length of 439 Bytes in the format

<xml>
  <data>
    AA5555AA056B0C31350600120076028A013A018[...]0000000000
  </data>
</xml>

thanks to the work of

"""
import logging

import defusedxml
import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import HTTPError, Timeout

from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)


class SolvisSC2XMLReader:
    """class to read and analyze solvis remote data."""

    def __init__(self, hostname, username, password) -> None:
        """Initialize the solvis data interpreter."""
        self.data = {}
        uri = f"""{hostname}/sc2_val.xml"""

        _LOGGER.debug("""URI: %s""", uri)

        try:
            basic = HTTPDigestAuth(username, password)
            response = requests.get(uri, stream=True, auth=basic, timeout=10)
        except Timeout as err:
            _LOGGER.debug("""GET Request: Timeout Exception -- %s""", err)
            return
        except HTTPError as err:
            _LOGGER.debug("""GET Request: HTTP Exception -- %s""", err)
            return

        _LOGGER.debug("Response Status: %s", response.status_code)

        if response.status_code == 200:  # OK, got something
            response.raw.decode_content = True

            sc2_data = defusedxml.ElementTree.parse(response.raw)
            root = sc2_data.getroot()
            payload_data = root.find("data")

            self.data = self.create_array_from_data(str(payload_data))

    def create_array_from_data(self, data_sc2: str):
        """Interprets the solvis remote data and transfors it into data_array."""
        data_array = {}
        value_int = 0
        value_float = 0.0

        # ersten Bereich übergehen, zu SC2 anscheinend gekürzt
        # value_ = string_[0: 11]
        # string_ = string_[11:]

        # Header
        # value_str = data_sc2[0:12]
        # print("Header: [{0}]".format(self.convertAtoH(value_str, 12)));
        data_sc2 = data_sc2[12:]

        # Uhrzeit
        # value_str = data_sc2[0:6]
        # print("Uhrzeit: [{0}]".format(self.convertAtoH(value_str, 6)));
        data_sc2 = data_sc2[6:]
        val1 = self.create_data_entry("time", "", now(), "")
        data_array["time"] = val1

        # Anlagentyp
        # value_str = data_sc2[0:4]
        # print("Anlagentyp: [{0}]".format(self.convertAtoH(value_str, 4)));
        data_sc2 = data_sc2[4:]

        # Systemnummer
        # value_str = data_sc2[0:4]
        # print("Systemnummer: [{0}]".format(self.convertAtoH(value_str, 4)));
        data_sc2 = data_sc2[4:]

        element_in_sc2_data = 0
        while element_in_sc2_data < 63:
            # Temps
            if element_in_sc2_data < 16:
                value_int = self.convert_data_to_int(data_sc2, 4)
                data_sc2 = data_sc2[4:]
                if value_int > 32767:
                    value_int = value_int - 65536
                value_float = value_int / 10

                the_name = f"S{element_in_sc2_data + 1}"
                val1 = self.create_data_entry(
                    the_name, "Temperature", value_float, "°C"
                )
                data_array[the_name] = val1
            elif element_in_sc2_data == 16:
                value_int = self.convert_data_to_int(data_sc2, 4)
                data_sc2 = data_sc2[4:]
                data_array["S18"] = self.create_data_entry(
                    "S17", "VSG Solar", value_int, "l/h"
                )
            elif element_in_sc2_data == 17:
                value_int = self.convert_data_to_int(data_sc2, 4)
                data_sc2 = data_sc2[4:]
                data_array["S17"] = self.create_data_entry(
                    "S18", "VSG Wasser", value_int, "l/h"
                )
            elif 18 <= element_in_sc2_data <= 20:
                # print("AnalogIn: [{0}]".format(self.convertAtoH(value_, 4)));
                data_sc2 = data_sc2[4:]
            elif 21 <= element_in_sc2_data <= 24:
                # print("AnalogOut: [{0}]".format(self.convertAtoH(value_, 2)));
                data_sc2 = data_sc2[2:]
            elif 25 <= element_in_sc2_data <= 27:
                value_int = self.convert_data_to_int(data_sc2, 4)
                data_sc2 = data_sc2[4:]
                if value_int > 32767:
                    value_int = value_int - 65536
                    # end if
                    value_float = value_int / 10
                    the_name = f"RF{element_in_sc2_data - 24}"
                    data_array[the_name] = self.create_data_entry(
                        the_name, "Raumfühler", value_float, "°C"
                    )
            elif 28 <= element_in_sc2_data <= 41:
                value_int = self.convert_data_to_int(data_sc2, 2)
                data_sc2 = data_sc2[2:]
                the_name = f"A{element_in_sc2_data - 27}"
                data_array[the_name] = self.create_data_entry(
                    the_name, "Output", value_int, ""
                )
            element_in_sc2_data += 1

        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["Z1"] = self.create_data_entry(
            "Z1", "Laufzeit Brenner", value_int, "h"
        )
        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["Z2"] = self.create_data_entry("Z2", "Starts Brenner", value_int, "")
        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["Z3"] = self.create_data_entry(
            "Z3", "Laufzeit Anforderung 2", value_int, ""
        )
        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["Z4"] = self.create_data_entry(
            "Z4", "Laufzeit Solarpumpe", value_int, "h"
        )
        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["SE"] = self.create_data_entry("SE", "Solarertrag", value_int, "kWh")

        # skip 30 Byte
        # value_str = data_sc2[0:30]
        data_sc2 = data_sc2[30:]

        value_int = self.convert_data_to_int(data_sc2, 4)
        data_sc2 = data_sc2[4:]
        data_array["SL"] = self.create_data_entry(
            "SL", "Solarleistung", value_int, "kW"
        )

        return data_array

    def print_data(self, array_=None):
        """Write sensor data to logger."""
        for value_ in array_:
            if value_["Key"][0:1] == "S":
                _LOGGER.debug(
                    value_["Key"] + "=>" + value_["Value"] + " - " + value_["Name"]
                )

    def create_data_entry(
        self, the_key=None, the_name=None, the_value=None, the_unit=None
    ) -> dict:
        """Return dictionary entry."""
        data_entry = {}
        data_entry["Key"] = the_key
        data_entry["Name"] = the_name
        data_entry["Value"] = the_value
        data_entry["Unit"] = the_unit
        return data_entry

    def convert_data_to_int(self, hex_string: str, size_: int) -> int:
        """Return integer value out of hex from solvis data."""
        hex_string = hex_string[0:size_]
        chunk_array = []
        element_count = 0
        while element_count < size_ / 2:
            sstr_ = hex_string[0:2]
            hex_string = hex_string[2:]
            chunk_array.append(sstr_)
            element_count += 1

        if len(hex_string):
            chunk_array.append(hex_string)

        arsz_ = len(chunk_array)
        while arsz_ > 0:
            hex_string += chunk_array[arsz_ - 1]
            arsz_ -= 1

        return int(hex_string, base=16)
