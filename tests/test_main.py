from unittest import TestCase
from testfixtures import Replacer, tempdir, compare, ShouldRaise, OutputCapture
from archivist.main import parse_command_line


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