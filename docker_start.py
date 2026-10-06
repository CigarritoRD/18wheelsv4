"""Prepare the mounted data volume, then drop privileges before starting the app."""
import os
from pathlib import Path
import sys

APP_UID = 10001
APP_GID = 10001


def prepare_data_directory(path: Path):
    path = path.resolve()
    if path == Path('/') or path == Path('/app') or path in Path('/app').parents:
        raise ValueError('Choose a dedicated data directory, normally /data.')
    path.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        os.chown(path, APP_UID, APP_GID)
        for parent, directories, files in os.walk(path, followlinks=False):
            for name in directories + files:
                item = Path(parent) / name
                info = item.lstat()
                if info.st_uid != APP_UID or info.st_gid != APP_GID:
                    os.chown(item, APP_UID, APP_GID, follow_symlinks=False)
    return path


def drop_privileges():
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(APP_GID)
        os.setuid(APP_UID)


def main():
    prepare_data_directory(Path(os.environ.get('EW_DATA_DIR', '/data')))
    drop_privileges()
    os.execv(sys.executable, [sys.executable, str(Path(__file__).with_name('run.py')), '--no-browser'])


if __name__ == '__main__':
    main()
