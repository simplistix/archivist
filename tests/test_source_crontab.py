from unittest import TestCase
from testfixtures import compare
from archivist.sources.crontab import Plugin
from tests.helpers import SingleCommandMixin


class TestPackages(SingleCommandMixin, TestCase):

    def test_simple(self):
        self.Popen.set_command('crontab -l -u foo', stdout=b'a crontab')
        plugin = Plugin(**Plugin.schema(dict(type='packages', name='foo')))
        plugin.process(self.dir.path)
        self.dir.compare(expected=['foo'])
        compare(b'a crontab', self.dir.read('foo'))
