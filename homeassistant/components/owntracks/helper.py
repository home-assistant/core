"""Helper for OwnTracks."""
try:
    import nacl
except ImportError:
    nacl = None


def supports_encryption() -> bool:
    """Test if we support encryption."""
    return nacl is not None
