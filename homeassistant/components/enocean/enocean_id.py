"""EnOceanID utilities for Home Assistant integration.

This module provides the EnOceanID class for handling EnOcean four byte (32 bit) addresses,
including parsing, validation, and conversion between integer and string formats.
"""


class EnOceanID:
    """Implementation of the EnOcean four byte (32 bit) addresses to identify devices.

    # A note about sending addresses
    Each EnOcean device has a unique ID (called *Chip ID*) which it can use
    for sending telegrams. Alternatively, EnOcean gateways can also use a range
    of 128 consecutive addresses for sending, starting at the so-called
    _Base ID_ of the gateway. A gateway's *Base ID* is a four byte address in
    the range FF:80:00:00 to FF:FF:FF:80. The Base ID is a predefined address,
    which can be changed by the user only a few times (at most 10 times for the
    TCM310 chip). The allowed addresses for sending a telegram are thus the
    following 129 addresses:

    - Chip ID (= device ID),
    - Base ID,
    - Base ID + 1,
    - Base ID + 2,
    - ...
    - Base ID + 126, and
    - Base ID + 127.

    All other addresses must not be used for sending (and will be rejected by
    official EnOcean modules). This is meant as a basic security feature. Have a
    look at the EnOcean [knowledge base](https://www.enocean.com/de/faq-knowledge-base/what-is-difference-between-base-id-and-chip-id/) for the official explanation of the differences between chip ID and base IDs.

    Base IDs are always in the range FF:80:00:00 to FF:FF:FF:80.
    """

    def __init__(self, id: int | str) -> None:
        """Initialize the EnOceanID from an integer or string."""
        enOceanID = -1
        if isinstance(id, str):
            enOceanID = EnOceanID.from_string(id).to_number()
        if isinstance(id, int):
            enOceanID = id
        if not isinstance(enOceanID, int):
            raise TypeError(
                "ID must be an integer or a hex string that can be converted to an integer."
            )
        if enOceanID < 0:
            raise ValueError("ID out of bounds (must be at least 0).")
        if enOceanID > 0xFFFFFFFF:
            raise ValueError(
                "ID out of bounds (must be smaller than 0xFFFFFFFF = 4294967295)."
            )
        self._id = enOceanID

    @classmethod
    def from_number(cls, id: int) -> "EnOceanID":
        """Create an EnOceanID instance from an integer."""
        return cls(id)

    @classmethod
    def from_string(cls, id_string: str) -> "EnOceanID":
        """Create an EnOceanID instance from a colon-separated string."""
        if not id_string:
            raise ValueError("from_string called with undefined argument")
        parts = id_string.strip().split(":")
        if len(parts) != 4:
            raise ValueError("Wrong format.")
        hex_string = "".join(part.zfill(2) for part in parts)
        return cls(int(hex_string, 16))

    @classmethod
    def broadcast(cls) -> "EnOceanID":
        """Return the broadcast ID (FF:FF:FF:FF)."""
        return cls(0xFFFFFFFF)

    @classmethod
    def validate_string(cls, id_string: str) -> bool:
        """Check that the supplied string is a valid EnOcean id."""
        parts = id_string.strip().split(":")

        if len(parts) != 4:
            return False

        hex_string = "".join(part.zfill(2) for part in parts)
        try:
            int(hex_string, 16)
        except ValueError:
            return False

        return True

    def to_number(self) -> int:
        """Return the EnOcean ID as integer."""
        return self._id

    def to_string(self) -> str:
        """Return the EnOcean ID as colon-separated hex string."""
        s = f"{self._id:08X}"
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}:{s[6:8]}"

    def to_json(self) -> str:
        """Return the EnOcean ID as JSON string."""
        return self.to_string()

    def __str__(self):
        """Return the EnOcean ID as string."""
        return self.to_string()
