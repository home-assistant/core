"""Critical sensor enums."""

import enum


class NotificationType(enum.Flag):
    """Type of notification in app's header."""

    CRITICAL = enum.auto()
    WARNING = enum.auto()
    ANY = CRITICAL | WARNING

    def to_string(self) -> str:
        """Convert flag to string.

        Returns:
            string flags representation.

        """
        return "|".join(str(flag.name).lower() for flag in self)
