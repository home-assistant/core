def custom_filter(fname):
    def custom_fiter_decorator(func):
        if not 'hass_custom_filters' in globals():
            globals()['hass_custom_filters'] = {}
        assert not fname in globals()['hass_custom_filters'], "Filter %s already registered" % fname
        globals()['hass_custom_filters'][fname] = func
        return func
    return custom_fiter_decorator