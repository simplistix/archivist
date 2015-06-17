from argparse import ArgumentParser, FileType

from .config import Config, ConfigError
def parse_command_line():
    parser = ArgumentParser()
    parser.add_argument('config',
                        help='Absolute path to the yaml config file',
                        type=FileType('r'))
    args = parser.parse_args()
    return args


class HandleKnownExceptions(object):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ConfigError:
            print('{}: {}'.format(exc_type.__name__, exc_val))
            raise SystemExit(1)
