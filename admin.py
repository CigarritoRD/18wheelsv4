"""Local server administrator utilities. Requires access to the private data directory.
Stop the server before backups so database and photo files are a consistent set.
"""
import argparse
import getpass
import os
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from app.server import create_app, password_hash, validate_password


def main():
    parser=argparse.ArgumentParser(description='18wheelers maintenance utilities')
    sub=parser.add_subparsers(dest='command',required=True)
    reset=sub.add_parser('reset-password',help='Reset an account when the admin cannot sign in')
    reset.add_argument('email')
    backup=sub.add_parser('backup',help='Back up the data directory; stop the server first')
    backup.add_argument('--output',default='backups')
    backup.add_argument('--server-stopped',action='store_true',required=True,help='Confirm the server is stopped')
    args=parser.parse_args()
    if args.command=='reset-password':
        app=create_app()
        password=getpass.getpass('New temporary password (12+ characters): ')
        if password!=getpass.getpass('Confirm: '):
            raise SystemExit('Passwords do not match.')
        try:validate_password(password)
        except Exception as error:raise SystemExit(getattr(error,'detail',str(error)))
        with app.state.db() as db:
            account=db.execute('SELECT id FROM users WHERE email=?',(args.email.strip().lower(),)).fetchone()
            if not account:raise SystemExit('No account with that email was found.')
            db.execute('UPDATE users SET password_hash=?,must_change=1 WHERE id=?',(password_hash(password),account['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(account['id'],))
        print('Password reset. The user must change it on their next login.')
    else:
        # Backups must not initialize the app or run a schema migration first.
        store=Path(os.environ.get('EW_DATA_DIR',Path(__file__).resolve().parent/'data')).resolve()
        if not (store/'jobs.sqlite3').is_file():
            raise SystemExit('No existing jobs database found in '+str(store))
        destination=Path(args.output).resolve()
        if destination==store or store in destination.parents:
            raise SystemExit('Choose a backup directory outside the data directory.')
        destination.mkdir(parents=True,exist_ok=True)
        # A stopped server and SQLite backup API avoid copying a partial WAL state.
        snapshot=destination/'.snapshot.sqlite3'
        source=sqlite3.connect(store/'jobs.sqlite3')
        target=sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        archive=destination/('18wheelers-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
        try:
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(snapshot,'data/jobs.sqlite3')
                for path in store.rglob('*'):
                    if path.is_file() and path.name not in ('jobs.sqlite3','jobs.sqlite3-shm','jobs.sqlite3-wal'):
                        z.write(path,'data/'+str(path.relative_to(store)))
        finally:snapshot.unlink(missing_ok=True)
        print('Backup created: '+str(archive))
        print('Keep this file private. It contains employee information and job photos.')

if __name__=='__main__':main()
