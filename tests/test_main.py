from unittest import TestCase

from testfixtures import Replacer, tempdir, compare, ShouldRaise, OutputCapture

from archivist.config import ConfigError
from archivist.main import parse_command_line, HandleKnownExceptions


class TestParseCommandLine(TestCase):

    def check(self, argv):
        with Replacer() as r:
            r.replace('sys.argv', ['x']+argv)
            return parse_command_line()

    @tempdir()
    def test_okay(self, dir):
        path = dir.write('test.yaml', 'foo')
        args = self.check([path])
        compare('foo', args.config.read())

    @tempdir()
    def test_not_okay(self, dir):
        path = dir.getpath('bad.yaml')
        with ShouldRaise(SystemExit(2)):
            with OutputCapture() as output:
                self.check([path])
        self.assertTrue("can't open" in output.captured)
        self.assertTrue(path in output.captured)

    @tempdir()
    def test_default(self, dir):
        dir.write('config.yaml', 'foo')
        with Replacer() as r:
            r.replace('archivist.config.default_repo_config.path', dir.path)
            args = self.check([])
        compare('foo', args.config.read())


class TestHandleKnownExceptions(TestCase):

    def test_config_error(self):
        with ShouldRaise(SystemExit(1)):
            with OutputCapture() as output:
                with HandleKnownExceptions():
                    raise ConfigError('foo', dict(x=1, y=2))
        # when the exception isn't caught, nothing should be printed
        output.compare('ConfigError: foo: \n'
                       'x: 1\n'
                       'y: 2\n')

    def test_value_error(self):
        with ShouldRaise(ValueError('foo')):
            with OutputCapture() as output:
                with HandleKnownExceptions():
                    raise ValueError('foo')
        # when the exception isn't caught, nothing should be printed
        output.compare('')