"""Utils for local file."""

import os


def check_file_path_access(file_path: str) -> bool:
    """Check that filepath given is readable."""
    if not os.access(file_path, os.R_OK):
        return False
    return True
