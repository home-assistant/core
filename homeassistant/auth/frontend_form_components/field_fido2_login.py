"""WebAuthn key authentication field."""
import voluptuous

from . import FrontendFormComponent


class Fido2LoginField(FrontendFormComponent):
    """
    Represents a frontend-fido2-login-field field.

    frontend-fido2-login-field takes auth_data as schema property in ordet to authenticate a user using WebAuthn.
    It returns the signature and the verification data as an object.
    """

    def __init__(self) -> None:
        """Init method."""
        super().__init__(
            "frontend-fido2-login-field", voluptuous.Schema({"auth_data": str})
        )
