"""Various utilities for Bang & Olufsen testing."""

from inflection import underscore

from homeassistant.components.bang_olufsen.const import (
    BEO_REMOTE_CONTROL_KEYS,
    BEO_REMOTE_KEYS,
    BEO_REMOTE_SUBMENU_CONTROL,
    BEO_REMOTE_SUBMENU_LIGHT,
    DEVICE_BUTTONS,
)

from .const import TEST_REMOTE_SERIAL, TEST_SERIAL_NUMBER


def get_button_entity_ids(id_prefix: str = "beosound_balance_11111111") -> list[str]:
    """Return a list of button entity_ids that Mozart devices (except Beoconnect Core and Beosound Premiere) provides."""
    return [
        f"event.{id_prefix}_{underscore(button_type)}".replace("preset", "favorite_")
        for button_type in DEVICE_BUTTONS
    ]


def get_remote_entity_ids(
    remote_serial: str = TEST_REMOTE_SERIAL, device_serial: str = TEST_SERIAL_NUMBER
) -> list[str]:
    """Return a list of entity_ids that the Beoremote One provides."""
    entity_ids: list[str] = []

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
