"""Common methods."""


def generate_entity_name(user_name: str) -> str:
    """Generate name."""

    return f"Globi {user_name.lower().capitalize()}"
