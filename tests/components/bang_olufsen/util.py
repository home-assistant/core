"""Various utilities for Bang & Olufsen testing."""

from inflection import underscore

from homeassistant.components.bang_olufsen.const import (
    BEO_REMOTE_CONTROL_KEYS,
    BEO_REMOTE_KEYS,
    BEO_REMOTE_SUBMENU_CONTROL,
    BEO_REMOTE_SUBMENU_LIGHT,
    DEVICE_BUTTONS,
)


def get_button_entity_ids() -> list[str]:
    """Return a list of entity_ids that Mozart devices (except Beoconnect Core) provides."""
    return [
        f"event.beosound_balance_11111111_{underscore(button_type)}".replace(
            "preset", "favourite_"
        )
        for button_type in DEVICE_BUTTONS
    ]


def get_remote_entity_ids() -> list[str]:
    """Return a list of entity_ids that the Beoremote One provides."""
    entity_ids: list[str] = []

    # Add remote light key Event entity ids
    entity_ids.extend(
        [
            f"event.beoremote_one_55555555_11111111_{BEO_REMOTE_SUBMENU_LIGHT.lower()}_{key_type.lower()}".replace(
                "func", "function_"
            ).replace("digit", "digit_")
            for key_type in BEO_REMOTE_KEYS
        ]
    )

    # Add remote control key Event entity ids
    entity_ids.extend(
        [
            f"event.beoremote_one_55555555_11111111_{BEO_REMOTE_SUBMENU_CONTROL.lower()}_{key_type.lower()}".replace(
                "func", "function_"
            ).replace("digit", "digit_")
            for key_type in (*BEO_REMOTE_KEYS, *BEO_REMOTE_CONTROL_KEYS)
        ]
    )

    return entity_ids
