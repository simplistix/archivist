from unittest import TestCase
from testfixtures import Replacer, TempDirectory, compare
from testfixtures.popen import MockPopen
from archivist.sources.packages import Plugin
from tests.helpers import ShouldFailSchemaWith


class TestPackages(TestCase):

    def setUp(self):
        self.dir = TempDirectory()
        self.addCleanup(self.dir.cleanup)
        self.Popen = MockPopen()
        r = Replacer()
        r.replace('archivist.helpers.Popen', self.Popen)
        self.addCleanup(r.restore)

    def test_rpm(self):
        self.Popen.set_command('rpm -qa', stdout=b'some packages')
        plugin = Plugin(**Plugin.schema(dict(type='packages', name='rpm')))
        plugin.process(self.dir.path)
        self.dir.compare(expected=['rpm'])
        compare(b'some packages', self.dir.read('rpm'))

    def test_dpkg(self):
        self.Popen.set_command('dpkg -l', stdout=b'some packages')
        plugin = Plugin(**Plugin.schema(dict(type='packages', name='dpkg')))
        plugin.process(self.dir.path)
        self.dir.compare(expected=['dpkg'])
        compare(b'some packages', self.dir.read('dpkg'))

    def test_wrong(self):
        text = "not a valid value for dictionary value @ data['name']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='packages', name='foo'))
