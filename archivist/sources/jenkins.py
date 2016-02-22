import os
from glob import glob

from os.path import join
from voluptuous import Schema, Required, All
from .paths import Plugin as Paths
from archivist.helpers import absolute_path


class Plugin(Paths):

    schema = Schema({
        'type': 'jenkins',
        Required('name', default='jenkins'): str,
        'repo': str,
        'path': All(str, absolute_path)
    })

    patterns = (
        ['*.xml'],
        ['jobs', '*', 'config.xml']
    )

    def __init__(self, type, name, repo, path):
        self.jenkins_root = path
        super(Plugin, self).__init__(type, name, repo, path)

    def relative_path(self, source_path, target_path):
        full_target = target_path+source_path[len(self.jenkins_root):]
        return full_target, full_target.split(os.sep)

    @staticmethod
    def _paths(jenkins_root, *patterns):
        for pattern in patterns:
            for path in glob(join(jenkins_root, *pattern)):
                yield path

    def expand_source_paths(self, jenkins_root):
        self.source_paths = [p for
                             p in self._paths(jenkins_root, *self.patterns)]

    def write_plugin_versions(self, jenkins_root, target_path):
        plugins = {}
        for manifest_path in self._paths(
            jenkins_root,
            ['plugins', '*', 'META-INF', 'MANIFEST.MF']
        ):
            data = {}
            with open(manifest_path) as manifest:
                for line in manifest: # pragma: no branch
                    parts = line.split(':', 1)
                    if len(parts) < 2:
                        continue
                    name, value = parts
                    key = name.lower().strip()
                    value = value.strip()
                    if key in data:
                        raise AssertionError((
                            'duplicate keys for %r found, '
                            'value was %r, now %r'
                            ) % (key, data[key], value))
                    data[key] = value

            # check what I think is true is actually true!
            for a, b in (('extension-name', 'implementation-title'),):
                if data[a] != data[b]:
                    raise AssertionError('%s (%r) != %s (%r)' % (
                        a, data[a], b, data[b]
                        ))

            name = data['extension-name']
            filename = manifest_path.split(os.sep)[-3]
            if name in plugins:
                raise AssertionError('%r and %r both said they were %r' % (
                    plugins[name][1], filename, name
                    ))
            plugins[name]= data['plugin-version'], filename

        with open(join(target_path, 'plugin-versions.txt'), 'w') as output:
            for name, info in sorted(plugins.items()):
                version, _ = info
                output.write('%s: %s\n' % (name, version))

    def process(self, target_path):
        jenkins_root = self.source_paths
        self.expand_source_paths(jenkins_root)
        super(Plugin, self).process(target_path)
        self.write_plugin_versions(jenkins_root, target_path)
