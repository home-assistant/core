"""Stream regular file contents to a backup from a separate process.

On Linux, closing a file descriptor releases all POSIX advisory locks held by
that process on the inode, including SQLite's locks on an unrelated descriptor.
The Home Assistant process therefore never opens files while building the tar.
"""

import json
from pathlib import Path
import sys

CHUNK_SIZE = 1024 * 1024


def main() -> None:
    """Serve file read requests on stdin, writing exactly size bytes to stdout."""
    commands = sys.stdin.buffer
    output = sys.stdout.buffer
    for line in commands:
        file_path, size = json.loads(line)
        remaining = size
        with Path(file_path).open("rb") as source:
            while remaining:
                data = source.read(min(CHUNK_SIZE, remaining))
                if not data:
                    raise OSError(f"Source changed during backup: {file_path}")
                output.write(data)
                remaining -= len(data)
        output.flush()


if __name__ == "__main__":
    main()
