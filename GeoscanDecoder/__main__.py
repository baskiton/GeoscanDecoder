import argparse
import configparser
import sys

from GeoscanDecoder import CONFIG, HOMEDIR, ui
from GeoscanDecoder.version import __version__


if __name__ == '__main__':
    cp = configparser.ConfigParser()
    cp.read_dict({'main': {'ip': '127.0.0.1',
                           'port': '8000',
                           'outdir': str(HOMEDIR),
                           'merge mode': 'off'},
                  'info': {'version': __version__}})
    cp.read(CONFIG)

    ap = argparse.ArgumentParser()

    ap.add_argument('--server', default=cp.get('main', 'ip'), help='Soundmodem connection IP')
    ap.add_argument('--port', default=cp.get('main', 'port'), help='Soundmodem connection port')
    ap.add_argument('--outdir', default=cp.get('main', 'outdir'), help='Directory to store received data')
    ap.add_argument('--merge', default=cp.get('main', 'merge mode'), help='Store all new images data to one file')
    ap.add_argument('--ui', help='Run in GUI', action='store_true')

    args = ap.parse_args()
    cp.set('main', 'ip', args.server or '127.0.0.1')
    cp.set('main', 'port', args.port or '8000')
    cp.set('main', 'outdir', str(args.outdir) or str(HOMEDIR))
    cp.set('main', 'merge mode', args.merge or 'off')

    frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    if args.ui or frozen:
        app = ui.App(cp)
        app.mainloop()

    with CONFIG.open('w') as cf:
        cp.write(cf)
