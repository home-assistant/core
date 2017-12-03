# pylint: disable=missing-docstring, too-many-arguments

class IHCDevice:
    """Base class for all ihc devices"""
    def __init__(self, ihccontroller, name, ihcid, ihcname: str, ihcnote: str, ihcposition: str):
        self.ihc = ihccontroller
        self._name = name
        self._ihcid = ihcid
        self.ihcname = ihcname
        self.ihcnote = ihcnote
        self.ihcposition = ihcposition

    @property
    def name(self):
        """Return the device name"""
        return self._name

    def get_ihcid(self) -> int:
        """Return the ihc resource id."""
        return self._ihcid

    def set_name(self, name):
        """Set the name"""
        self._name = name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self.ihc.info:
            return {}
        return {
            'ihcid': self._ihcid,
            'ihcname' : self.ihcname,
            'ihcnote' : self.ihcnote,
            'ihcposition' : self.ihcposition
        }
