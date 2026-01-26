"""TFA.me station integration: helper.py."""


def resolve_tfa_host(address: str) -> str:
    """Resolve user input into a usable host for TFA.me."""

    # If the address contains a dash, assume it's a station ID and
    # build the mDNS hostname. Otherwise, assume it's an IP or hostname.
    address = address.strip()
    if "-" in address:
        # Example: "XXX-XXX-XXX" -> "tfa-me-xxx-xxx-xxx.local"
        return f"tfa-me-{address.lower()}.local"

    return address
