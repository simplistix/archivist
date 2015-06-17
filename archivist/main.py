from argparse import ArgumentParser, FileType

def parse_command_line():
    parser = ArgumentParser()
    parser.add_argument('config',
                        help='Absolute path to the yaml config file',
                        type=FileType('r'))
    args = parser.parse_args()
    return args
