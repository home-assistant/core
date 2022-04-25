"""WebAuthn key registration field."""
import voluptuous

from . import FrontendFormComponent


class Fido2RegisterField(FrontendFormComponent):
    """
    Represents a frontend-fido2-register-field field.

    frontend-fido2-register-field takes registration_data as schema for initialization and should return
    a webauthn attestation.
    """

    def __init__(self) -> None:
        """Init method."""
        super().__init__(
            "frontend-fido2-register-field",
            voluptuous.Schema({"registration_data": str}),
        )
