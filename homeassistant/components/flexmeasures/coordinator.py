class S2FlexMeasuresClient:
    """
    todo: Just a stub! Instead, use: `from flexmeasures_client import S2FlexMeasuresClient`
    """
    system_description: dict

    def parse_message(self, message):
        """Update system description by parsing message."""
        self.system_description = message
