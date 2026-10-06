import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import pytest
from docker_start import prepare_data_directory


def test_refuses_root_directory():
    with pytest.raises(ValueError):
        prepare_data_directory(Path('/'))


@pytest.mark.skipif(os.geteuid() != 0 or int(Path('/proc/self/uid_map').read_text().split()[2]) < 10002, reason='Runtime does not map UID 10001; container privilege change cannot be exercised here')
def test_root_owned_volume_becomes_writable_after_privilege_drop():
    folder = Path(tempfile.mkdtemp(prefix='18w-volume-', dir='/tmp'))
    try:
        (folder/'old.sqlite3').write_bytes(b'existing-data')
        script = '''
import os
from pathlib import Path
from docker_start import prepare_data_directory, drop_privileges
folder = Path(os.environ['TEST_VOLUME'])
prepare_data_directory(folder)
drop_privileges()
assert os.geteuid() == 10001 and os.getegid() == 10001
assert (folder/'old.sqlite3').read_bytes() == b'existing-data'
(folder/'old.sqlite3').write_bytes(b'updated-data')
(folder/'new-file').write_text('writable')
'''
        result = subprocess.run([sys.executable,'-c',script], env={**os.environ,'TEST_VOLUME':str(folder)}, capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
        assert (folder/'new-file').stat().st_uid == 10001
        assert (folder/'old.sqlite3').read_bytes() == b'updated-data'
    finally:
        shutil.rmtree(folder)


def test_bootstrap_prepares_volume_then_drops_privileges_before_launch(monkeypatch, tmp_path):
    import docker_start
    events = []
    monkeypatch.setenv('EW_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(docker_start, 'prepare_data_directory', lambda path: events.append(('prepare', path)))
    monkeypatch.setattr(docker_start, 'drop_privileges', lambda: events.append(('drop',)))
    monkeypatch.setattr(docker_start.os, 'execv', lambda executable, args: events.append(('launch', args)))
    docker_start.main()
    assert [event[0] for event in events] == ['prepare', 'drop', 'launch']
    assert events[2][1][-1] == '--no-browser'
    assert events[2][1][-2].endswith('run.py')
