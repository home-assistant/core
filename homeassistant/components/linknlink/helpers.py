"""Helper functions for the linknlink integration."""


def format_mac(mac):
    """Format a MAC address."""
    return ":".join([format(octet, "02x") for octet in mac])
