"""Constants for the NAD Infrared integration."""

from enum import StrEnum

DOMAIN = "nad_infrared"
CONF_DEVICE_TYPE = "device_type"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"


class NADDeviceType(StrEnum):
    """NAD device types."""

    RECEIVER = "receiver"
    AMPLIFIER = "amplifier"
    TUNER = "tuner"
    CD_PLAYER = "cd_player"
    TAPE_DECK = "tape_deck"


DEVICE_NAMES: dict[NADDeviceType, str] = {
    NADDeviceType.RECEIVER: "NAD receiver",
    NADDeviceType.AMPLIFIER: "NAD amplifier",
    NADDeviceType.TUNER: "NAD tuner",
    NADDeviceType.CD_PLAYER: "NAD CD player",
    NADDeviceType.TAPE_DECK: "NAD cassette deck",
}
