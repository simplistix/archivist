import os
from unittest import TestCase
import sys

from testfixtures import TempDirectory, compare, ShouldRaise, OutputCapture
from archivist.helpers import run, CalledProcessError


class TestRun(TestCase):

    def run_command(self, code, **kw):
        with TempDirectory() as dir:
            self.path = dir.write('test.py', code+'\n')
            with OutputCapture() as output:
                result = run([sys.executable, self.path], **kw)
            output.compare('')
        return result

    def test_stdout(self):
        result = self.run_command("import sys; sys.stdout.write('okay')")
        compare(result, 'okay')

    def test_stderr(self):
        with ShouldRaise(CalledProcessError) as s:
            self.run_command("import sys; sys.stderr.write('bad')")
        compare(str(s.raised), """\
{command} went wrong:
returncode: 0

stdout:

stderr:
bad
""".format(command=[sys.executable, self.path]))

    def test_returncode(self):
        with ShouldRaise(CalledProcessError) as s:
            self.run_command("import sys; sys.exit(13)")
        compare(str(s.raised), """\
{command} went wrong:
returncode: 13

stdout:

stderr:

""".format(command=[sys.executable, self.path]))

    def test_working_directory(self):
        with TempDirectory() as somewhere:
            # dance 'cos of weird mac temp directories
            previous = os.getcwd()
            os.chdir(somewhere.path)
            expected = os.getcwd()
            os.chdir(previous)

            result = self.run_command("import os; print os.getcwd()",
                                      cwd=somewhere.path)
            compare(result, expected+'\n')

    def test_with_shell(self):
        with OutputCapture() as output:
            result = run('echo "hello out there"', shell=True)
        output.compare('')
        compare(result, 'hello out there\n')

