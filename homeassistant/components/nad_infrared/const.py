"""Constants for the NAD Infrared integration."""

from enum import StrEnum

DOMAIN = "nad_infrared"
CONF_DEVICE_TYPE = "device_type"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"


class NADDeviceType(StrEnum):
    """NAD device types."""

    RECEIVER = "receiver"
    AMPLIFIER = "amplifier"
    CD_PLAYER = "cd_player"
    CASSETTE_DECK = "cassette_deck"


DEVICE_NAMES: dict[NADDeviceType, str] = {
    NADDeviceType.RECEIVER: "NAD receiver",
    NADDeviceType.AMPLIFIER: "NAD amplifier",
    NADDeviceType.CD_PLAYER: "NAD CD player",
    NADDeviceType.CASSETTE_DECK: "NAD cassette deck",
}
