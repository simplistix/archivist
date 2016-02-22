import os
from grp import getgrgid
from pwd import getpwuid
from stat import (
    S_IRUSR, S_IXUSR, S_IRGRP, S_IWGRP, S_IXGRP, S_IROTH, S_IWOTH, S_IXOTH
)
from stat import S_IWUSR

from voluptuous import Schema, All, Length

from archivist.helpers import ensure_dir_exists, absolute_path
from archivist.plugins import Source


class Plugin(Source):

    schema = Schema(dict(type='paths', name=None, repo=str,
                         values=All([All(str, absolute_path)],
                                    Length(min=1))))

    def __init__(self, type, name, repo, values):
        super(Plugin, self).__init__(type, name, repo)
        self.source_paths = values

    @staticmethod
    def path_attributes(source_path):
        stat = os.stat(source_path)
        perms = ''
        for bit, char in zip((
            S_IRUSR, S_IWUSR, S_IXUSR,
            S_IRGRP, S_IWGRP, S_IXGRP,
            S_IROTH, S_IWOTH, S_IXOTH,
        ),
            'rwx'*3):
            perms += (char if stat.st_mode & bit else '-')
        return (
            perms,
            getpwuid(stat.st_uid).pw_name,
            getgrgid(stat.st_gid).gr_name
        )

    @staticmethod
    def read_contents_file(contents_path):
        contents = {}
        if os.path.exists(contents_path):
            with open(contents_path) as contents_file:
                for line in contents_file:
                    perms, owner, group, path = line.split()
                    contents[path] = perms, owner, group
        return contents

    @staticmethod
    def write_contents_file(contents, contents_path):
        ensure_dir_exists(os.path.split(contents_path)[0])
        with open(contents_path, 'w') as contents_file:
            owner_width = 0
            group_width = 0
            for perms, owner, group in contents.values():
                owner_width = max(owner_width, len(owner))
                group_width = max(group_width, len(group))

            for absolute_path, meta in sorted(contents.items()):
                perms, owner, group = meta
                contents_file.write(
                    '{perms} {owner:{owner_width}} {group:{group_width}} '
                    '{path}\n'.format(
                    perms = perms,
                    owner = owner,
                    owner_width = owner_width,
                    group = group,
                    group_width = group_width,
                    path = absolute_path,
                    ))


    def relative_path(self, source_path, target_path):
        split_path = (target_path.split(os.sep) + source_path.split(os.sep)[1:])
        full_target = os.sep.join(split_path)
        return full_target, split_path

    def handle_one(self, source_path, target_path, contents):
        contents[source_path] = self.path_attributes(source_path)

        full_target, split_path = self.relative_path(source_path, target_path)
        directory = os.sep.join(split_path[:-1])

        ensure_dir_exists(directory)

        with open(source_path, 'rb') as source:
            with open(full_target, 'wb') as target:
                target.write(source.read())

    def process(self, target_path):

        contents_path = os.path.join(target_path, 'contents.txt')
        old_contents = self.read_contents_file(contents_path)
        new_contents = {}

        for source_path in self.source_paths:
            if os.path.isfile(source_path):
                self.handle_one(source_path, target_path, new_contents)
            else:
                for root, dirs, filenames in os.walk(source_path):
                    for filename in filenames:
                        self.handle_one(os.path.join(root, filename),
                                        target_path,
                                        new_contents)

        to_delete = set(old_contents) - set(new_contents)
        for path in to_delete:
            full_target, split_path = self.relative_path(path, target_path)
            os.remove(full_target)
            while True:
                split_path.pop()
                directory = os.sep.join(split_path)
                if os.listdir(directory):
                    break
                os.rmdir(directory)

        self.write_contents_file(new_contents, contents_path)
