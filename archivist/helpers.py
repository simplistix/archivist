import os
from subprocess import Popen, PIPE


def ensure_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


class CalledProcessError(Exception):
    """This exception is raised when a process run by check_call() or
    check_output() returns a non-zero exit status.
    The exit status will be stored in the returncode attribute;
    check_output() will also store the output in the output attribute.
    """
    def __init__(self, command, returncode, stdout, stderr):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return (
            "{command!r} went wrong:\n"
            "returncode: {returncode}\n\n"
            "stdout:\n"
            "{stdout}\n"
            "stderr:\n"
            "{stderr}\n".format(**self.__dict__))


def run(command, cwd=None):
    process = Popen(command, stdout=PIPE, stderr=PIPE, cwd=cwd)
    out, err = process.communicate()
    if err or process.returncode:
        raise CalledProcessError(command, process.returncode,
                                 out, err)
    return out