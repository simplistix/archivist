from __future__ import absolute_import

import os
from unittest import TestCase

from testfixtures import TempDirectory, compare, ShouldRaise

from archivist.plugins import Source
from archivist.sources.jenkins import Plugin
from tests.helpers import ShouldFailSchemaWith
from tests.test_source_paths import PathsHelper


class TestJenkinsSource(TestCase):

    def setUp(self):
        self.dir = TempDirectory()
        self.addCleanup(self.dir.cleanup)

    def test_abc(self):
        self.assertTrue(issubclass(Plugin, Source))

    def test_schema_max(self):
        compare(
            dict(type='jenkins', name='core', repo='config',
                 path=self.dir.path),
            actual=Plugin.schema(
                dict(type='jenkins', name='core', repo='config',
                     path=self.dir.path)
            ))

    def test_schema_min(self):
        compare(
            dict(type='jenkins', name='jenkins',
                 repo='config', path=self.dir.path),
            actual=Plugin.schema(
                dict(type='jenkins', repo='config',
                     path=self.dir.path)
            ))

    def test_schema_wrong_type(self):
        text = "expected str for dictionary value @ data['path']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='bar', path=['/']))

    def test_schema_extra_keys(self):
        with ShouldFailSchemaWith("extra keys not allowed @ data['foo']"):
            Plugin.schema(dict(type='jenkins', foo='bar'))

    def test_invalid_name(self):
        text = "expected str for dictionary value @ data['name']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='jenkins', name=[]))

    def test_no_path(self):
        text = "'' does not exist for dictionary value @ data['path']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='jenkins', path=''))

    def test_path_not_string(self):
        text = "expected str for dictionary value @ data['path']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='jenkins', path=1))

    def test_path_not_there(self):
        invalid = self.dir.getpath('foo')
        text = "'%s' does not exist for dictionary value @ data['path']" % (
            invalid
        )
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='jenkins', path=invalid))

    def test_interface(self):
        plugin = Plugin('source', name='jenkins', repo='config',
                        path='root')
        compare(plugin.type, 'source')
        compare(plugin.name, 'jenkins')
        compare(plugin.repo, 'config')
        compare(plugin.source_paths, 'root')


class TestJenkinsSourceWithFileTree(PathsHelper, TestCase):

    def make_plugin(self):
        return Plugin('source', 'jenkins', 'config', self.dir.getpath('source'))

    def test_simple(self):
        p1, _ = self.write_file('nodeMonitors.xml', 'nodeMonitors')
        p2, _ = self.write_file('another.xml', 'another')
        p3, _ = self.write_file('jobs/test-multi/config.xml', 'multi-config')
        p4, _ = self.write_file('jobs/test-another/config.xml', 'single-config')
        p5, _ = self.write_file('jobs/test-another/workspace/junk.xml', 'junk')

        plugin = self.make_plugin()
        plugin.process(self.dir.getpath('target'))

        compare(self.dir.read('target/nodeMonitors.xml'), 'nodeMonitors')
        compare(self.dir.read('target/another.xml'), 'another')
        compare(self.dir.read('target/jobs/test-multi/config.xml'),
                'multi-config')
        compare(self.dir.read('target/jobs/test-another/config.xml'),
                'single-config')
        compare(self.dir.read('target/plugin-versions.txt'),
                '')
        compare(self.dir.read('target/contents.txt'), ''.join([
            "rwxrwxrwx {} {}\n".format(self.user_group, p2),
            "rwxrwxrwx {} {}\n".format(self.user_group, p4),
            "rwxrwxrwx {} {}\n".format(self.user_group, p3),
            "rwxrwxrwx {} {}\n".format(self.user_group, p1),
        ]))

    def _write_jpi(self, name, manifest):
        self.dir.write('plugins/'+name+'/META-INF/MANIFEST.MF', manifest)

    def test_plugin_versions(self):
        self._write_jpi('test1', """
Url: http://wiki.jenkins-ci.org/display/JENKINS/Ant+Plugin
Junk: 1.0
Extension-Name: test1
Implementation-Title: test1
Implementation-Version: 2
Plugin-Version: 2
""")
        self._write_jpi('test2', """
Junk: 1.0
Extension-Name: test2
Implementation-Title: test2
Implementation-Version: 1
Plugin-Version: 1
""")

        plugin = self.make_plugin()
        plugin.write_plugin_versions(self.dir.path, self.dir.path)

        compare(
            self.dir.read(self.dir.getpath('plugin-versions.txt')),
            expected=os.linesep.join((
                'test1: 2',
                'test2: 1',
                '',
            )))

    def test_extension_name_versus_implementation_title(self):
        self._write_jpi('test1', """
Junk: 1.0
Extension-Name: test1
Implementation-Title: Test1
Implementation-Version: 2
Plugin-Version: 2
""")
        plugin = self.make_plugin()
        with ShouldRaise(AssertionError(
            "extension-name ('test1') != implementation-title ('Test1')"
            )):
            plugin.write_plugin_versions(self.dir.path, self.dir.path)

    def test_duplicate_key(self):
        self._write_jpi('test1', """
Extension-Name: test1
Extension-Name: test2
""")
        plugin = self.make_plugin()
        with ShouldRaise(AssertionError(
            "duplicate keys for 'extension-name' found, "
            "value was 'test1', now 'test2'")):
            plugin.write_plugin_versions(self.dir.path, self.dir.path)

    def test_duplicate_name(self):
        self._write_jpi('test1', """
Junk: 1.0
Extension-Name: test1
Implementation-Title: test1
Implementation-Version: 2
Plugin-Version: 2
""")
        self._write_jpi('test2', """
Junk: 1.0
Extension-Name: test1
Implementation-Title: test1
Implementation-Version: 1
Plugin-Version: 1
""")
        plugin = self.make_plugin()
        with ShouldRaise(AssertionError(
            "'test1' and 'test2' both said they were 'test1'"
            )):
            plugin.write_plugin_versions(self.dir.path, self.dir.path)

    def test_development_plugin(self):
        self._write_jpi('test', """
Extension-Name: dropdown-viewstabbar-plugin
Implementation-Title: dropdown-viewstabbar-plugin
Implementation-Version: 1.6-SNAPSHOT
Plugin-Version: 1.6-SNAPSHOT (private-06/29/2012 15:10-hudson)
""")

        plugin = self.make_plugin()
        plugin.write_plugin_versions(self.dir.path, self.dir.path)

        compare(
            self.dir.read(self.dir.getpath('plugin-versions.txt')),
            expected=os.linesep.join((
                'dropdown-viewstabbar-plugin: 1.6-SNAPSHOT (private-06/29/2012 15:10-hudson)',
                '',
            )))
