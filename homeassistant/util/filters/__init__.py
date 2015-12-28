hass_custom_filters = {}
def custom_filter(fname):
    def custom_fiter_decorator(func):
        global hass_custom_filters
        assert not fname in hass_custom_filters, "Filter %s already registered" % fname
        hass_custom_filters[fname] = func
        return func
    return custom_fiter_decorator