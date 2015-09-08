from collections import defaultdict
from unittest import TestCase

from testfixtures import ShouldRaise, Replacer, compare

from archivist.plugins import Plugins


plugin1 = object()
plugin2 = object()
plugin3 = object()
plugin4 = object()


class MockEntryPoint(object):
    def __init__(self, name, obj):
        self.name, self.obj = name, obj
    def load(self):
        return self.obj


class TestPluginLoading(TestCase):

    def mock_iter_entry_points(self, group):
        return self.entry_points[group]

    def setUp(self):
        self.entry_points = defaultdict(list)

    def load_plugins(self):
        with Replacer() as r:
            r.replace('archivist.plugins.iter_entry_points',
                      self.mock_iter_entry_points)
            plugins = Plugins.load()
        return plugins

    def test_no_plugins(self):
        plugins = self.load_plugins()
        with ShouldRaise(KeyError('foo')):
            plugins.get('notification', 'foo')
        with ShouldRaise(KeyError('foo')):
            plugins.get('repo', 'foo')
        with ShouldRaise(KeyError('foo')):
            plugins.get('source', 'foo')

    def test_one_notification_plugin(self):
        self.entry_points['archivist.notification'].append(
            MockEntryPoint('foo', plugin1)
        )
        plugins = self.load_plugins()
        compare(plugin1, plugins.get('notification', 'foo'))
        with ShouldRaise(KeyError('foo')):
            plugins.get('repo', 'foo')
        with ShouldRaise(KeyError('foo')):
            plugins.get('source', 'foo')

    def test_one_repo_plugin(self):
        self.entry_points['archivist.repo'].append(
            MockEntryPoint('foo', plugin1)
        )
        plugins = self.load_plugins()
        with ShouldRaise(KeyError('foo')):
            plugins.get('notification', 'foo')
        compare(plugin1, plugins.get('repo', 'foo'))
        with ShouldRaise(KeyError('foo')):
            plugins.get('source', 'foo')

    def test_one_source_plugin(self):
        self.entry_points['archivist.source'].append(
            MockEntryPoint('foo', plugin1)
        )
        plugins = self.load_plugins()
        with ShouldRaise(KeyError('foo')):
            plugins.get('notification', 'foo')
        with ShouldRaise(KeyError('foo')):
            plugins.get('repo', 'foo')
        compare(plugin1, plugins.get('source', 'foo'))

    def test_multiple_plugins(self):
        self.entry_points['archivist.notification'].append(
            MockEntryPoint('foo', plugin1)
        )
        self.entry_points['archivist.notification'].append(
            MockEntryPoint('bar', plugin2)
        )
        self.entry_points['archivist.repo'].append(
            MockEntryPoint('baz', plugin3)
        )
        self.entry_points['archivist.source'].append(
            MockEntryPoint('foo', plugin4)
        )
        plugins = self.load_plugins()
        compare(plugin1, plugins.get('notification', 'foo'))
        compare(plugin2, plugins.get('notification', 'bar'))
        compare(plugin3, plugins.get('repo', 'baz'))
        compare(plugin4, plugins.get('source', 'foo'))

    def test_plugin_names(self):
        # check setup.py is as expected!
        plugins = Plugins.load()
        actual = []
        for type, stuff in sorted(plugins.plugins.items()):
            for name in sorted(stuff):
                actual.append((type, name))
        compare([
            ('notification', 'stream'),
            ('repo', 'git'),
            ('source', 'crontab'),
            ('source', 'packages'),
            ('source', 'paths'),
        ],actual)
