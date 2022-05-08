"""Helper for OwnTracks."""
try:
    import nacl
except ImportError:
    nacl = None  # type: ignore[assignment]


def supports_encryption() -> bool:
    """Test if we support encryption."""
    return nacl is not None
