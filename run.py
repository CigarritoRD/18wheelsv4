"""Launch locally or as a hosted FastAPI service."""
import argparse
import os
import threading
import webbrowser
from pathlib import Path
import uvicorn
from app.server import create_app


def main():
    parser=argparse.ArgumentParser(description='18wheelers Jobs server')
    parser.add_argument('--host',default=os.environ.get('EW_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8080')))
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    app=create_app()
    with app.state.db() as conn:
        first_run=conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
    local=f'http://127.0.0.1:{args.port}'
    url=local
    if first_run:
        token=app.state.setup_token
        url+='/?setup_token='+token
    print('\n18WHEELERS JOBS\n'+'='*42)
    print('Workspace: '+local)
    print('Database: '+app.state.database.backend)
    print('Photo storage: '+app.state.photo_store.kind)
    if app.state.database.backend=='sqlite':
        print('Data directory: '+str(app.state.store))
    if first_run:
        if os.environ.get('EW_SETUP_TOKEN'):
            print('\nFIRST-TIME SETUP: open /?setup_token=<EW_SETUP_TOKEN> on your HTTPS domain.')
            print('The configured token is intentionally not written to application logs.')
        else:
            print('\nFIRST-TIME SETUP (private link):\n'+url)
            print('On an HTTPS host, replace the local address with your HTTPS domain.')
    if args.host not in ('localhost','127.0.0.1','::1'):
        print('\nShared deployment: use HTTPS, EW_SECURE_COOKIES=1, and the deployment guide.')
    print('\nKeep this window open while using the app. Press Ctrl+C to stop.\n')
    if not args.no_browser and args.host in ('localhost','127.0.0.1','::1'):
        threading.Timer(1.2,lambda:webbrowser.open(url)).start()
    # Access logs are off to avoid logging first-run setup tokens in URL queries.
    uvicorn.run(app,host=args.host,port=args.port,access_log=False,proxy_headers=False)

if __name__=='__main__':
    main()
