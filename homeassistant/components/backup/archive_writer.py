"""Create a Core backup archive without opening Recorder files in Home Assistant.

POSIX advisory locks can be released when the owning process closes any file
handle to a locked inode. All configuration files are therefore opened here.
"""

import io
import json
from pathlib import Path, PurePath
import sys
import tarfile
import time

from securetar import SecureTarArchive, atomic_contents_add


def main() -> None:
    """Build the archive using securetar's public interface in this process."""
    request = json.loads(sys.stdin.buffer.readline())
    backup_json = sys.stdin.buffer.read()

    def is_excluded(path: PurePath) -> bool:
        return any(
            path.full_match(f"data/{pattern}") for pattern in request["excludes"]
        )

    with SecureTarArchive(
        Path(request["archive_path"]),
        "w",
        bufsize=request["buf_size"],
        create_version=request["create_version"],
        password=request["password"],
    ) as outer:
        backup_info = tarfile.TarInfo(name="./backup.json")
        backup_info.size = len(backup_json)
        backup_info.mtime = int(time.time())
        outer.tar.addfile(backup_info, fileobj=io.BytesIO(backup_json))
        with outer.create_tar("./homeassistant.tar.gz", gzip=True) as core:
            atomic_contents_add(
                tar_file=core,
                origin_path=Path(request["config_path"]),
                file_filter=is_excluded,
                arcname="data",
            )


if __name__ == "__main__":
    main()
