from __future__ import absolute_import

from grp import getgrgid
import os
from pwd import getpwuid
from unittest import TestCase

from testfixtures import compare, TempDirectory

from archivist.plugins import Source
from archivist.sources.paths import Plugin
from tests.helpers import ShouldFailSchemaWith


class TestPathSource(TestCase):

    def test_abc(self):
        self.assertTrue(issubclass(Plugin, Source))

    def test_schema_ok(self):
        compare(dict(type='path', values=['/foo', '/bar']),
                Plugin.schema(dict(type='path', values=['/foo', '/bar'])))

    def test_schema_wrong_type(self):
        text = "not a valid value for dictionary value @ data['type']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='bar', values=['/']))

    def test_schema_extra_keys(self):
        with ShouldFailSchemaWith("extra keys not allowed @ data['foo']"):
            Plugin.schema(dict(type='path', foo='bar'))

    def test_name_supplied(self):
        text = "not a valid value for dictionary value @ data['name']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='path', name='foo'))

    def test_no_paths(self):
        text = "length of value must be at least 1 for dictionary value " \
               "@ data['values']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='path', values=[]))

    def test_path_not_string(self):
        text = "invalid list value @ data['values'][0]"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='path', values=[1]))

    def test_path_not_starting_with_slash(self):
        text = "invalid list value @ data['values'][0]"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='path', values=['foo']))

    def test_interface(self):
        plugin = Plugin('source', name=None, repo='config',
                        values=['/foo/bar'])
        compare(plugin.type, 'source')
        compare(plugin.name, None)
        compare(plugin.repo, 'config')
        compare(plugin.source_paths, ['/foo/bar'])

class TestPathSourceWithTempDir(TestCase):

    def setUp(self):
        self.dir = TempDirectory()
        self.addCleanup(self.dir.cleanup)
        usr_entry = getpwuid(os.getuid())
        self.user_group = '{} {}'.format(
            usr_entry.pw_name,
            getgrgid(usr_entry.pw_gid).gr_name,
        )

    def test_read_contents_file(self):
        path = self.dir.write('contents.txt', '''\
r-x-wx--- x y /foo/bar
rwxr-x--- a b /baz/bob
''')

        contents = Plugin.read_contents_file(path)

        compare(contents, {
            '/foo/bar': ('r-x-wx---', 'x', 'y'),
            '/baz/bob': ('rwxr-x---', 'a', 'b'),
        })

    def test_write_contents_file(self):
        contents = {
            '/b':   ('r-x-wx---', 'looong', 'group'),
            '/a/d': ('rw-r-x---', 'short', 'grouuuup'),
            '/a/c': ('rwxr-x---', 'x', 'y'),
        }

        contents_path = self.dir.getpath('contents.txt')
        Plugin.write_contents_file(contents, contents_path)

        compare("""\
rwxr-x--- x      y        /a/c
rw-r-x--- short  grouuuup /a/d
r-x-wx--- looong group    /b
""", self.dir.read(contents_path))


    def write_file(self, path, content, perms, root='source/'):
        file_path = self.dir.write(root + path, content)
        os.chmod(file_path, perms)
        relative_path = file_path[1:]
        return file_path, relative_path

    def make_plugin(self, *paths):
        return Plugin('source', None, 'config',
                      [self.dir.getpath(p) for p in paths])

    def test_single_file(self):
        file_path, relative_path = self.write_file('afile', 'foo', 0777)

        plugin = self.make_plugin('source/afile')
        plugin.process(self.dir.getpath('target'))

        self.dir.compare(path='target',
                         expected=['contents.txt', relative_path],
                         files_only=True)

        compare(self.dir.read('target/' + relative_path), 'foo')
        compare(self.dir.read('target/contents.txt'),
                "rwxrwxrwx {} {}\n".format(self.user_group, file_path))

    def test_tree(self):
        a_path, a_rel = self.write_file('a', 'foo', 0777)
        b_path, b_rel = self.write_file('b', 'bar', 0700)
        d_path, d_rel = self.write_file('c/d', 'baz', 0600)

        plugin = self.make_plugin('source')
        plugin.process(self.dir.getpath('target'))

        self.dir.compare(path='target',
                         expected=['contents.txt', a_rel, b_rel, d_rel],
                         files_only=True)

        compare(self.dir.read('target/' + a_rel), 'foo')
        compare(self.dir.read('target/' + b_rel), 'bar')
        compare(self.dir.read('target/' + d_rel), 'baz')
        compare(self.dir.read('target/contents.txt'), ''.join([
                "rwxrwxrwx {} {}\n".format(self.user_group, a_path),
                "rwx------ {} {}\n".format(self.user_group, b_path),
                "rw------- {} {}\n".format(self.user_group, d_path),
                ]))

    def test_removes_missing_files(self):
        plugin = self.make_plugin('source')
        a_path, a_rel = self.write_file('c/a', 'foo', 0777)
        b_path, b_rel = self.write_file('d/b', 'bar', 0777)

        plugin.process(self.dir.getpath('target'))
        os.remove(b_path)
        plugin.process(self.dir.getpath('target'))

        self.dir.compare(path='target',
                         expected=['contents.txt', a_rel],
                         files_only=True)

        b_container = self.dir.getpath('target/' + os.path.split(b_rel)[0])
        self.failIf(os.path.exists(b_container))

        compare(self.dir.read('target/contents.txt'),
                "rwxrwxrwx {} {}\n".format(self.user_group, a_path))

    def test_two_paths_side_by_side(self):
        a_path, a_rel = self.write_file('a', 'foo', 0777)
        b_path, b_rel = self.write_file('b', 'bar', 0700)

        # two plugins
        plugin = self.make_plugin(a_path, b_path)
        plugin.process(self.dir.getpath('target'))

        self.dir.compare(path='target',
                         expected=['contents.txt', a_rel, b_rel],
                         files_only=True)

        compare(self.dir.read('target/' + a_rel), 'foo')
        compare(self.dir.read('target/' + b_rel), 'bar')
        compare(self.dir.read('target/contents.txt'), ''.join([
                "rwxrwxrwx {} {}\n".format(self.user_group, a_path),
                "rwx------ {} {}\n".format(self.user_group, b_path),
                ]))
