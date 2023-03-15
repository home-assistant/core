"""Managers for each table."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import Recorder


class BaseTableManager:
    """Base class for table managers."""

    def __init__(self, recorder: "Recorder") -> None:
        """Initialize the table manager."""
        self.active = False
        self.recorder = recorder
