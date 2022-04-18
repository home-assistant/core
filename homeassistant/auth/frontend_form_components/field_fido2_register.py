import voluptuous

from . import FrontendFormComponent


class Fido2RegisterField(FrontendFormComponent):
    def __init__(self) -> None:
        super().__init__(
            "frontend-fido2-register-field",
            voluptuous.Schema({"registration_data": str}),
        )
