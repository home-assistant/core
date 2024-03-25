"""Define tests for the The Things Network."""


def add_schema_suggestion(schema, user_input):
    """Add suggested value for key in voluptuous schema."""
    user_input = dict(user_input)
    for k in schema:
        if k.description and "suggested_value" in k.description:
            user_input.setdefault(k, k.description["suggested_value"])
    return user_input
