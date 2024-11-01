"""Common classes and elements for Omnilogic Integration."""


def check_guard(state_key, item, entity_setting):
    """Validate that this entity passes the defined guard conditions defined at setup."""

    if state_key not in item:
        return True

    for guard_condition in entity_setting["guard_condition"]:
        if guard_condition and all(
            item.get(guard_key) == guard_value
            for guard_key, guard_value in guard_condition.items()
        ):
            return True

    return False
