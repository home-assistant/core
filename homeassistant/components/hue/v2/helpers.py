"""Helper functions for Philips Hue v2."""


def normalize_hue_brightness(brightness):
    """Return calculated brightness values."""
    if brightness is not None:
        # Hue uses a range of [0, 100] to control brightness.
        brightness = float((brightness / 255) * 100)

    return brightness


def normalize_hue_transition(transition):
    """Return rounded transition values."""
    if transition is not None:
        # hue transition duration is in milliseconds and round them to 100ms
        transition = int(round(transition, 1) * 1000)

    return transition
