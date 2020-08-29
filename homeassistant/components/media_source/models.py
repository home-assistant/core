"""Media Source models."""
from dataclasses import dataclass
import datetime
from typing import List


@dataclass
class Media:
    """Represent a media file."""

    source: str
    name: str
    location: str
    mime_type: str = None
    media_type: str = None
    is_file: bool = False
    is_dir: bool = False
    created: datetime = None
    modified: datetime = None
    children: List = None
