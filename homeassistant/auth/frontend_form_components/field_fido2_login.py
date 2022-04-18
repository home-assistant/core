import voluptuous

from . import FrontendFormComponent


class Fido2LoginField(FrontendFormComponent):
    def __init__(self) -> None:
        super().__init__(
            "frontend-fido2-login-field", voluptuous.Schema({"auth_data": str})
        )
