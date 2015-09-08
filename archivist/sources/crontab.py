from os.path import join
from voluptuous import Schema
from archivist.helpers import run
from archivist.plugins import Source


class Plugin(Source):

    schema = Schema(dict(type='packages', name=str))

    def process(self, path):
        output = run(['crontab', '-l', '-u', self.name])
        with open(join(path, self.name), 'w') as stream:
            stream.write(output)
