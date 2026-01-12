"""Various utilities for Bang & Olufsen testing."""

from inflection import underscore

from homeassistant.components.bang_olufsen.const import (
    BEO_REMOTE_CONTROL_KEYS,
    BEO_REMOTE_KEYS,
    BEO_REMOTE_SUBMENU_CONTROL,
    BEO_REMOTE_SUBMENU_LIGHT,
    DEVICE_BUTTONS,
)

from .const import (
    TEST_BATTERY_CHARGING_BINARY_SENSOR_ENTITY_ID,
    TEST_BATTERY_SENSOR_ENTITY_ID,
    TEST_MEDIA_PLAYER_ENTITY_ID,
    TEST_MEDIA_PLAYER_ENTITY_ID_2,
    TEST_MEDIA_PLAYER_ENTITY_ID_3,
    TEST_MEDIA_PLAYER_ENTITY_ID_4,
    TEST_REMOTE_SERIAL,
    TEST_SERIAL_NUMBER,
)


def _get_button_entity_ids(id_prefix: str = "beosound_balance_11111111") -> list[str]:
    """Return a list of button entity_ids that Mozart devices provide.

    Beoconnect Core, Beosound A5, Beosound A9 and Beosound Premiere do not have (all of the) physical buttons and need filtering.
    """
    return [
        f"event.{id_prefix}_{underscore(button_type)}".replace("preset", "favorite_")
        for button_type in DEVICE_BUTTONS
    ]


def get_balance_entity_ids() -> list[str]:
    """Return a list of entity_ids that a Beosound Balance provides."""
    return [TEST_MEDIA_PLAYER_ENTITY_ID, *_get_button_entity_ids()]


def get_premiere_entity_ids() -> list[str]:
    """Return a list of entity_ids that a Beosound Premiere provides."""
    buttons = [
        TEST_MEDIA_PLAYER_ENTITY_ID_3,
        *_get_button_entity_ids("beosound_premiere_33333333"),
    ]
    buttons.remove("event.beosound_premiere_33333333_bluetooth")
    buttons.remove("event.beosound_premiere_33333333_microphone")
    return buttons


def get_a5_entity_ids() -> list[str]:
    """Return a list of entity_ids that a Beosound A5 provides."""
    buttons = [
        TEST_MEDIA_PLAYER_ENTITY_ID_4,
        TEST_BATTERY_SENSOR_ENTITY_ID,
        TEST_BATTERY_CHARGING_BINARY_SENSOR_ENTITY_ID,
        *_get_button_entity_ids("beosound_a5_44444444"),
    ]
    buttons.remove("event.beosound_a5_44444444_microphone")
    return buttons


def get_core_entity_ids() -> list[str]:
    """Return a list of entity_ids that a Beoconnect core provides."""
    return [TEST_MEDIA_PLAYER_ENTITY_ID_2]


def get_remote_entity_ids(
    remote_serial: str = TEST_REMOTE_SERIAL, device_serial: str = TEST_SERIAL_NUMBER
) -> list[str]:
    """Return a list of entity_ids that the Beoremote One provides."""
    entity_ids: list[str] = [
        f"sensor.beoremote_one_{remote_serial}_{device_serial}_battery"
    ]

    # Add remote light key Event entity ids
    entity_ids.extend(
        [
            f"event.beoremote_one_{remote_serial}_{device_serial}_{BEO_REMOTE_SUBMENU_LIGHT.lower()}_{key_type.lower()}".replace(
                "func", "function_"
            ).replace("digit", "digit_")
            for key_type in BEO_REMOTE_KEYS
        ]
    )

    # Add remote control key Event entity ids
    entity_ids.extend(
        [
            f"event.beoremote_one_{remote_serial}_{device_serial}_{BEO_REMOTE_SUBMENU_CONTROL.lower()}_{key_type.lower()}".replace(
                "func", "function_"
            ).replace("digit", "digit_")
            for key_type in (*BEO_REMOTE_KEYS, *BEO_REMOTE_CONTROL_KEYS)
        ]
    )

    return entity_ids
