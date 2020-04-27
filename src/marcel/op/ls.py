import argparse
import sys

import marcel.core
import marcel.object.error
import marcel.object.file
import marcel.op.filenames


SUMMARY = '''
The specified files, directories, and symlinks are written to the output stream.
'''


DETAILS = '''
Generates a stream of Files, representing files, directories and symlinks.

The flags {-0}, {-1}, and {-r} are mutually exclusive. {-1} is the default.

Flags {-f}, {-d}, and {-s} may be combined. If none of these flags are specified, then files, directories
and symlinks are all listed.

If no {filename}s are provided, then the currentn directory is listed.
'''


def ls():
    return Ls()


class LsArgParser(marcel.core.ArgParser):

    def __init__(self, env):
        super().__init__('ls', env, ['-0', '-1', '-r', '-f', '--file', '-d', '--dir', '-s', '--symlink'],
                         SUMMARY, DETAILS)
        depth_group = self.add_mutually_exclusive_group()
        depth_group.add_argument('-0',
                                 action='store_true',
                                 dest='d0',
                                 help='Do not descend into directories, (i.e., expore to depth 0)')
        depth_group.add_argument('-1',
                                 action='store_true',
                                 dest='d1',
                                 help='''Descend into directories listed on the command line,
                                  (i.e., explore to depth 1)''')
        depth_group.add_argument('-r', '--recursive',
                                 action='store_true',
                                 dest='dr',
                                 help='Descend into all directories, recursively')
        self.add_argument('-f', '--file',
                          action='store_true',
                          help='Include files in output')
        self.add_argument('-d', '--dir',
                          action='store_true',
                          help='Include directories in output')
        self.add_argument('-s', '--symlink',
                          action='store_true',
                          help='Include symbolic links in output')
        self.add_argument('filename',
                          nargs=argparse.REMAINDER,
                          help='A filename or glob pattern')


class Ls(marcel.op.filenames.FilenamesOp):

    def __init__(self):
        super().__init__(op_has_target=False)
        self.d0 = False
        self.d1 = False
        self.dr = False
        self.file = False
        self.dir = False
        self.symlink = False
        self.base = None
        self.emitted = set()

    def __repr__(self):
        if self.d0:
            depth = '0'
        elif self.d1:
            depth = '1'
        else:
            depth = 'recursive'
        include = ''
        if self.file:
            include += 'f'
        if self.dir:
            include += 'd'
        if self.symlink:
            include += 's'
        filenames = [str(p) for p in self.filename] if self.filename else '?'
        return f'ls(depth={depth}, include={include}, filename={filenames})'

    # BaseOp

    def doc(self):
        return __doc__

    def setup_1(self):
        super().setup_1()
        if len(self.roots) == 0:
            self.roots = [self.current_dir]
        if not (self.d0 or self.d1 or self.dr):
            self.d1 = True
        if not (self.file or self.dir or self.symlink):
            self.file = True
            self.dir = True
            self.symlink = True
        if len(self.roots) == 1:
            root = self.roots[0]
            self.base = root if root.is_dir() else root.parent
        else:
            self.base = None
            self.roots = sorted(self.roots)

    # Op

    def must_be_first_in_pipeline(self):
        return True

    # FilenamesOp

    def action(self, source):
        self.visit(source, 0)

    # For use by this class

    def visit(self, root, level):
        self.send_path(root)
        if root.is_dir() and ((level == 0 and (self.d1 or self.dr)) or self.dr):
            try:
                for file in sorted(root.iterdir()):
                    self.visit(file, level + 1)
            except PermissionError:
                self.send(marcel.object.error.Error(f'Cannot explore {root}: permission denied'))

    def send_path(self, path):
        s = path.is_symlink()
        f = path.is_file() and not s
        d = path.is_dir() and not s
        if ((self.file and f) or (self.dir and d) or (self.symlink and s)) and path not in self.emitted:
            file = marcel.object.file.File(path, self.base)
            self.send(file)
            self.emitted.add(path)
