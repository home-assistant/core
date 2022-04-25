"""Hidden field to carry state or additionaln data."""
import voluptuous

from . import FrontendFormComponent


class HiddenField(FrontendFormComponent):
    """Represents a frontend hidden field named frontend-hidden-field containing a default property in the schema."""

    def __init__(self) -> None:
        """Init method."""
        super().__init__("frontend-hidden-field", voluptuous.Schema({"default": str}))
