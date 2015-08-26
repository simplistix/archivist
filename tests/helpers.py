from testfixtures import ShouldRaise, compare
from voluptuous import MultipleInvalid


class ShouldFailSchemaWith(ShouldRaise):

    def __init__(self, message):
        super(ShouldFailSchemaWith, self).__init__(MultipleInvalid)
        self.message = message

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(ShouldFailSchemaWith, self).__exit__(exc_type, exc_val, exc_tb)
        compare(self.message, str(self.raised))
        return True