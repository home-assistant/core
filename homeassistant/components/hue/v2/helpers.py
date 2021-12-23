"""Helper functions for Philips Hue v2."""


def brightness_helper(brightness):
    """Returns calculated brightness values"""

    if brightness is not None:
        # Hue uses a range of [0, 100] to control brightness.
        brightness = float((brightness / 255) * 100)

    return brightness


def transition_helper(transition):
    """Returns rounded transition values"""

    if transition is not None:
        # hue transition duration is in milliseconds and round them to 100ms
        transition = int(round(transition, 1) * 1000)

    return transition
