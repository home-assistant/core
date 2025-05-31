class AuthenticationRequest:
    def __init__(self, email: str, password: str, type_client: str = "ANDROID"):
        self.email = email
        self.password = password
        self.type_client = type_client

    def to_dict(self):
        return self.__dict__
