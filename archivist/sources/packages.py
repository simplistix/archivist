from voluptuous import Any
from voluptuous import Schema
from archivist.helpers import run
from archivist.plugins import Source
from os.path import join

package_managers = dict(
    dpkg='-l',
    rpm='-qa',
)

class Plugin(Source):

    schema = Schema(dict(type='packages', name=Any(*package_managers)))

    def process(self, path):
        output = run([self.name, package_managers[self.name]])
        with open(join(path, self.name), 'w') as stream:
            stream.write(output)
