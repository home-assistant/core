ATTR_POWER = 'power'

CLIMATE_CONTROLLERS = []

class ClimateController:
    def __init__(self, config, logger):
        pass

    def initialize(self):
        return False

    @property
    def poll(self):
        return None

    @property
    def id(self):
        return None

    @property
    def name(self):
        return None

    @property
    def debug(self):
        return False
        
    def update_state(self):
        return False

    def set_property(self, property_name, new_value):
        return False

    def get_property(self, property_name):
        return None

    @property
    def state_attributes(self):
        raise NotImplementedError()

    @property
    def temperature_unit(self):
        raise NotImplementedError()

    @property
    def service_schema_map(self):
        return None

    @property
    def operations(self):
        """ Return a list of available operations """
        return []

    @property
    def attributes(self):
        """ Return a list of available attributes """
        return []

def register_controller(controller):
    """Decorate a function to register a controller."""
    CLIMATE_CONTROLLERS.append(controller)
    return controller

def create_controller(type, config, logger) -> ClimateController:
    for ctrl in CLIMATE_CONTROLLERS:
        if ctrl.match_type(type):
            c = ctrl(config, logger)
            if c.initialize():
                return c
            else:
                logger.error("climate_ip: error while initializing controller for type {}!".format(type))
    logger.error("climate_ip: controller for type {} not found!".format(type))
    return None

