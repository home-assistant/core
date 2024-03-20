"""Utils module with different functions and helpers."""


def replace_ip_prefix(original_string, new_prefix) -> str:
    """Split the original string into parts divided by the first dot."""
    parts = original_string.split(".", 1)

    # Check if the split operation found at least two parts
    if len(parts) > 1:
        # Replace the first part with new_prefix and rejoin with the rest of the string
        updated_string = f"{new_prefix}.{parts[1]}"
    else:
        # If there's no dot in the original string, return it unchanged
        # or handle this case as you see fit
        updated_string = original_string

    return updated_string
