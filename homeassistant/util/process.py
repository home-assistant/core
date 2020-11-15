"""Util to handle processes."""

import subprocess


def kill_subprocess(process: subprocess.Popen) -> None:
    """Force kill a subprocess and wait for it to exit."""
    process.kill()
    process.communicate()
    process.wait()

    del process
