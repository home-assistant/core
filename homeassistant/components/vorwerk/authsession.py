"""Auth sessions for pybotvac."""
import pybotvac


class VorwerkSession(pybotvac.PasswordlessSession):
    """PasswordlessSession pybotvac session for Vorwerk cloud."""

    # The client_id is the same for all users.
    CLIENT_ID = "KY4YbVAvtgB7lp8vIbWQ7zLk3hssZlhR"

    def __init__(self):
        """Initialize Vorwerk cloud session."""
        super().__init__(client_id=VorwerkSession.CLIENT_ID, vendor=pybotvac.Vorwerk())

    @property
    def token(self):
        """Return the token dict. Contains id_token, access_token and refresh_token."""
        return self._token
