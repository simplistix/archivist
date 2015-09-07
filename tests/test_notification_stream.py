from logging import getLogger, INFO
from unittest import TestCase
from testfixtures import LogCapture, OutputCapture, compare
from archivist.config import default_notifications_config
from archivist.notifications.stream import Plugin
from tests.helpers import ShouldFailSchemaWith

logger = getLogger()

class PluginTests(TestCase):

    def full_cycle(self, **kw):
        params = dict(type='stream', name='stdout')
        params.update(kw)
        with LogCapture():
            with OutputCapture(separate=True) as output:
                plugin = Plugin(**Plugin.schema(params))
                logger.info('before')
                plugin.start()
                logger.info('during-info')
                logger.error('during-error')
                plugin.finish()
                logger.info('after')
        return output

    def test_schema_minimal(self):
        compare(dict(type='stream', name='stdout', level=INFO,
                     fmt=None, datefmt=None),
                Plugin.schema(dict(type='stream', name='stdout')))

    def test_schema_maximal(self):
        compare(dict(type='stream', name='stdout', level=INFO,
                     fmt='foo', datefmt='bar'),
                Plugin.schema(dict(type='stream', name='stdout', level='InFo',
                                   fmt='foo', datefmt='bar')))

    def test_schema_default(self):
        output = self.full_cycle(**default_notifications_config)
        output.compare(stderr='during-info\n'
                              'during-error\n')

    def test_schema_invalid_stream_name(self):
        text = "not a valid value for dictionary value @ data['name']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='stream', name='stdfoo'))

    def test_schema_integer_level(self):
        compare(dict(type='stream', name='stdout', level=0,
                     fmt=None, datefmt=None),
                Plugin.schema(dict(type='stream', name='stdout', level=0)))

    def test_schema_invalid_string_level(self):
        text = "no log level named 'foo' for dictionary value @ data['level']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(type='stream', name='stderr', level='foo'))

    def test_level(self):
        output = self.full_cycle(name='stdout', level='WARNING')
        output.compare(stdout='during-error\n')

    def test_stdout(self):
        output = self.full_cycle(name='stdout')
        output.compare(stdout='during-info\n'
                              'during-error\n')

    def test_stderr(self):
        output = self.full_cycle(name='stderr')
        output.compare(stderr='during-info\n'
                              'during-error\n')

    def test_format(self):
        output = self.full_cycle(fmt='%(levelname)s %(message)s')
        output.compare(stdout='INFO during-info\n'
                              'ERROR during-error\n')

    def test_time_format(self):
        output = self.full_cycle(fmt='%(asctime)s %(message)s',
                                 datefmt='foo')
        output.compare(stdout='foo during-info\n'
                              'foo during-error\n')
