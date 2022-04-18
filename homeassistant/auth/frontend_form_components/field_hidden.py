import voluptuous

from . import FrontendFormComponent


class HiddenField(FrontendFormComponent):
    def __init__(self) -> None:
        super().__init__("frontend-hidden-field", voluptuous.Schema({"default": str}))
