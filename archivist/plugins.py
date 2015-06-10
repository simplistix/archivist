from collections import defaultdict
from pkg_resources import iter_entry_points


class Plugins(object):

    def __init__(self):
        self.plugins = defaultdict(dict)

    def load(self):
        for type in 'notification', 'repo', 'source':
            for entrypoint in iter_entry_points(group='archivist.'+type):
                plugin = entrypoint.load()
                self.register(type, entrypoint.name, plugin)

    def register(self, type, name, plugin):
        self.plugins[type][name] = plugin

    def get(self, type, name):
        return self.plugins[type][name]
