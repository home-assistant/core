"""Basic mock functions and objects related to the HomeKit component."""
PATH_HOMEKIT = 'homeassistant.components.homekit'


def get_patch_paths(name=None):
    """Return paths to mock 'add_preload_service'."""
    path_acc = PATH_HOMEKIT + '.accessories.add_preload_service'
    path_file = PATH_HOMEKIT + '.' + str(name) + '.add_preload_service'
    return (path_acc, path_file)


def mock_preload_service(acc, service, chars=None, opt_chars=None):
    """Mock alternative for function 'add_preload_service'."""
    service = MockService(service)
    if chars:
        chars = chars if isinstance(chars, list) else [chars]
        for char_name in chars:
            service.add_characteristic(char_name)
    if opt_chars:
        opt_chars = opt_chars if isinstance(opt_chars, list) else [opt_chars]
        for opt_char_name in opt_chars:
            service.add_characteristic(opt_char_name)
    acc.add_service(service)
    return service


class MockAccessory():
    """Define all attributes and methods for a MockAccessory."""

    def __init__(self, name):
        """Initialize a MockAccessory object."""
        self.display_name = name
        self.services = []

    def __repr__(self):
        """Return a representation of a MockAccessory. Use for debugging."""
        serv_list = [serv.display_name for serv in self.services]
        return "<accessory \"{}\", services={}>".format(
            self.display_name, serv_list)

    def add_service(self, service):
        """Add service to list of services."""
        self.services.append(service)

    def get_service(self, name):
        """Retrieve service from service list or return new MockService."""
        for serv in self.services:
            if serv.display_name == name:
                return serv
        serv = MockService(name)
        self.add_service(serv)
        return serv


class MockService():
    """Define all attributes and methods for a MockService."""

    def __init__(self, name):
        """Initialize a MockService object."""
        self.characteristics = []
        self.opt_characteristics = []
        self.display_name = name

    def __repr__(self):
        """Return a representation of a MockService. Use for debugging."""
        char_list = [char.display_name for char in self.characteristics]
        opt_char_list = [
            char.display_name for char in self.opt_characteristics]
        return "<service \"{}\", chars={}, opt_chars={}>".format(
            self.display_name, char_list, opt_char_list)

    def add_characteristic(self, char):
        """Add characteristic to char list."""
        self.characteristics.append(char)

    def add_opt_characteristic(self, char):
        """Add characteristic to opt_char list."""
        self.opt_characteristics.append(char)

    def get_characteristic(self, name):
        """Get char for char lists or return new MockChar."""
        for char in self.characteristics:
            if char.display_name == name:
                return char
        for char in self.opt_characteristics:
            if char.display_name == name:
                return char
        char = MockChar(name)
        self.add_characteristic(char)
        return char


class MockChar():
    """Define all attributes and methods for a MockChar."""

    def __init__(self, name):
        """Initialize a MockChar object."""
        self.display_name = name
        self.properties = {}
        self.value = None
        self.type_id = None
        self.setter_callback = None

    def __repr__(self):
        """Return a representation of a MockChar. Use for debugging."""
        return "<char \"{}\", value={}>".format(
            self.display_name, self.value)

    def set_value(self, value, should_notify=True, should_callback=True):
        """Set value of char."""
        self.value = value
        if self.setter_callback is not None and should_callback:
            # pylint: disable=not-callable
            self.setter_callback(value)

    def get_value(self):
        """Get char value."""
        return self.value


class MockTypeLoader():
    """Define all attributes and methods for a MockTypeLoader."""

    def __init__(self, class_type):
        """Initialize a MockTypeLoader object."""
        self.class_type = class_type

    def get(self, name):
        """Return a MockService or MockChar object."""
        if self.class_type == 'service':
            return MockService(name)
        elif self.class_type == 'char':
            return MockChar(name)
