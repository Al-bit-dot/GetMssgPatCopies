#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GetMssgPatCopies - finds the patent copies in a folder that are zero bytes in
size (the ones that did not download) and writes two lists of them, so they
can be fetched again.

Runs on Python 3.4 and later with only the standard library.  When tkinter is
available (it comes with the Windows installers from python.org) it opens a
window; otherwise it asks its questions in the terminal.

    python3 GetMssgPatCopies.py                 window if possible, else terminal
    python3 GetMssgPatCopies.py --console       terminal, even if a window is possible
    python3 GetMssgPatCopies.py FOLDER --yes    no questions: generate the lists for FOLDER now
    python3 GetMssgPatCopies.py --help          all options

Files it writes, in the chosen folder:
    MssgPat-Order.txt        the missing numbers, one per line (Fetcher Format, Windows line endings)
    MssgPat-USPTO-Order.txt  one line for the USPTO Patent Public Search box:
                             ("9123456" or "20020123457").pn.
"""

import argparse
import datetime
import json
import os
import re
import sys

VERSION = '1.0'
DESCRIPTION = ('GetMssgPatCopies finds the patent copies in a folder that are zero bytes in size and '
               'writes their numbers to MssgPat-Order.txt (Fetcher Format) and MssgPat-USPTO-Order.txt '
               '(a search for the USPTO Patent Public Search page).')

ORDER_NAME = 'MssgPat-Order.txt'
USPTO_NAME = 'MssgPat-USPTO-Order.txt'

# ---------------------------------------------------------------------------
# CORE-START  (pure logic, no user interface; number rules as in PatCopyPrint)
# ---------------------------------------------------------------------------

ONE_LETTER = ('D', 'H', 'T', 'X')             # followed by up to 7 digits
TWO_LETTER = ('RE', 'RD', 'RX', 'AI', 'PP')   # followed by up to 6 digits
FIRST_PUB_YEAR = 2001

# A patent copy's file name without its extension: 09123456, 9123456, D0512345,
# 20020123457, and the archive spellings US9123456B2, USD512345S, US20020123457A1.
_NAME_RE = re.compile(r'^(?:US)?[-_ ]?([A-Z]{0,2})[-_ ]?(\d{1,11})(?:[-_ ]?[A-Z]\d?)?$', re.ASCII)


def canon_from_name(name, year):
    """The standard form of the US number a file is named after, or None.

    Patents become 8 characters (09123456, D0512345, RE045678) and published
    applications 11 digits (20020123457), the same forms PatCopyPrint writes.
    """
    stem = os.path.splitext(name)[0].strip().upper()
    m = _NAME_RE.match(stem)
    if not m:
        return None
    pfx, digits = m.group(1), m.group(2)
    if not re.search(r'[1-9]', digits):
        return None
    if pfx == '':
        if len(digits) <= 8:
            return digits.rjust(8, '0')
        if len(digits) in (10, 11):
            y = int(digits[:4])
            if FIRST_PUB_YEAR <= y <= year and re.search(r'[1-9]', digits[4:]):
                return digits[:4] + digits[4:].rjust(7, '0')
        return None
    maxlen = 7 if pfx in ONE_LETTER else 6 if pfx in TWO_LETTER else 0
    if not maxlen or len(digits) > maxlen:
        return None
    return pfx + digits.rjust(maxlen, '0')


def sort_canons(canons):
    """Patents by number, then published applications, then prefixed documents.

    The same order as PatCopyPrint's "Sorted" and RemoveDupNumbers.
    """
    def group(c):
        if re.match(r'^\d{11}$', c):
            return 1
        return 0 if c[0].isdigit() else 2
    return sorted(canons, key=lambda c: (group(c), c))


def uspto_number(canon):
    """A number as the Patent Public Search page takes it in a .pn. search.

    Patents are 7 characters with leading zeros where needed and a letter prefix
    counting towards the 7 (09123456 -> 9123456, D0512345 -> D512345,
    RE045678 -> RE45678); 8-digit patents and published applications are kept.
    """
    if re.match(r'^\d{11}$', canon):
        return canon
    m = re.match(r'^([A-Z]*)(\d+)$', canon)
    pfx, digits = m.group(1), m.group(2).lstrip('0')
    return pfx + digits.rjust(max(7 - len(pfx), len(digits)), '0')


def order_text(canons):
    """The Fetcher Format list: one number per line, Windows line endings."""
    return ''.join(c + '\r\n' for c in canons)


def uspto_text(canons):
    """One line for the search box: ("9123456" or "20020123457").pn."""
    return '(' + ' or '.join('"%s"' % uspto_number(c) for c in canons) + ').pn.\r\n'


def survey(entries, year):
    """Sorts out a folder listing, given as [(file name, size in bytes)].

    Returns a dict with
      missing      the numbers whose copies are all zero bytes, sorted
      files        {number: [zero-byte file names]} for those numbers
      have_copy    zero-byte files left out because the same number also has a copy with content
      not_patents  zero-byte files whose names are not US patent or publication numbers
      copies       how many files are named after a US number
    """
    zero, full = {}, set()
    not_patents, copies = [], 0
    for name, size in entries:
        canon = canon_from_name(name, year)
        if canon is None:
            if size == 0:
                not_patents.append(name)
            continue
        copies += 1
        if size == 0:
            zero.setdefault(canon, []).append(name)
        else:
            full.add(canon)
    missing = sort_canons([c for c in zero if c not in full])
    have_copy = sorted(n for c in zero if c in full for n in zero[c])
    return {'missing': missing, 'files': dict((c, sorted(zero[c])) for c in missing),
            'have_copy': have_copy, 'not_patents': sorted(not_patents), 'copies': copies}


# CORE-END
# ---------------------------------------------------------------------------


# ---- Files and settings ----

CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.getmssgpatcopies.json')
DEFAULTS = {'folder': '', 'geometry': ''}


class Config(object):
    """Remembered settings in ~/.getmssgpatcopies.json (the last folder, the window size)."""

    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k in DEFAULTS:
                    if k in loaded and isinstance(loaded[k], type(DEFAULTS[k])):
                        self.data[k] = loaded[k]
        except Exception:
            pass

    def get(self, key):
        return self.data[key]

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            pass


def write_text(path, text):
    """Writes text exactly (its own line endings), as UTF-8."""
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def list_folder(folder):
    """(sub-folders, [(file name, size)]) of a folder, sorted the way a file manager sorts them."""
    dirs, files = [], []
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.isdir(full):
            dirs.append(name)
        elif os.path.isfile(full):
            try:
                files.append((name, os.path.getsize(full)))
            except OSError:
                pass
    dirs.sort(key=natural_key)
    files.sort(key=lambda f: natural_key(f[0]))
    return dirs, files


class Job(object):
    """One run over one folder: reads it and writes the two lists into it."""

    def __init__(self, folder, year=None):
        self.folder = os.path.abspath(folder)
        self.year = year or datetime.date.today().year
        self.result = survey(list_folder(self.folder)[1], self.year)
        missing = self.result['missing']
        self.files = [(ORDER_NAME, order_text(missing)), (USPTO_NAME, uspto_text(missing))] if missing else []

    def existing(self):
        return [n for n, _ in self.files if os.path.exists(os.path.join(self.folder, n))]

    def write(self):
        for n, text in self.files:
            write_text(os.path.join(self.folder, n), text)

    def summary(self):
        """What was found and saved, as lines for the status area."""
        r = self.result
        lines = []
        if r['missing']:
            lines.append('Saved "%s" and "%s" in %s.' % (ORDER_NAME, USPTO_NAME, self.folder))
            lines.append('%s with a zero-byte copy, out of %s named after a US number.'
                         % (plural(len(r['missing']), 'number'), plural(r['copies'], 'file')))
        elif r['copies']:
            lines.append('None of the %s named after a US number is zero bytes; nothing was saved.'
                         % plural(r['copies'], 'file'))
        else:
            lines.append('No files named after a US patent or publication number are in %s; nothing was saved.'
                         % self.folder)
        if r['have_copy']:
            lines.append('Left out because the same number also has a copy with content: %s.'
                         % ', '.join(r['have_copy']))
        if r['not_patents']:
            lines.append('Zero-byte files not named after a US number (left out): %s.'
                         % ', '.join(r['not_patents']))
        return lines

    def details(self):
        """The numbers found and the two files' contents, for the details area."""
        r = self.result
        rows = ['%-12s %s' % (c, ', '.join(r['files'][c])) for c in r['missing']]
        return ('Missing (%d), in order:\n%s\n\n%s:\n%s'
                % (len(rows), '\n'.join(rows), USPTO_NAME, uspto_text(r['missing']).rstrip()))


def plural(n, word):
    return '%d %s%s' % (n, word, '' if n == 1 else 's')


# ---- Console mode ----

def say(text=''):
    """print() that never fails on a Windows console with a limited code page."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def ask(prompt, default=''):
    """input() with a default shown in brackets; EOF (Ctrl-D / Ctrl-Z) means quit."""
    shown = ' [%s]' % default if default else ''
    try:
        answer = input('%s%s: ' % (prompt, shown)).strip()
    except (EOFError, KeyboardInterrupt):
        say()
        raise SystemExit(1)
    return answer if answer else default


def ask_yes_no(prompt, default=True):
    while True:
        a = ask(prompt + (' (Y/n)' if default else ' (y/N)')).lower()
        if a == '':
            return default
        if a in ('y', 'yes'):
            return True
        if a in ('n', 'no'):
            return False


def console_pick_folder(cfg):
    folder = cfg.get('folder')
    if not folder or not os.path.isdir(folder):
        folder = os.getcwd()
    while True:
        try:
            dirs, files = list_folder(folder)
        except OSError as e:
            say('Cannot list %s: %s' % (folder, e))
            folder = os.path.dirname(folder) or os.getcwd()
            continue
        say()
        say('Folder: ' + folder)
        entries = [os.path.dirname(folder)] if os.path.dirname(folder) != folder else []
        if entries:
            say('  %3d  ..' % 1)
        for d in dirs:
            entries.append(os.path.join(folder, d))
            say('  %3d  %s%s' % (len(entries), d, os.sep))
        say('  (%s here, %s zero bytes)' % (plural(len(files), 'file'), len([f for f in files if f[1] == 0])))
        say('Type g to generate the lists for this folder, the number of a folder to open it, '
            'a path to go to, or q to quit.')
        a = ask('Folder', 'g')
        if a.lower() in ('q', 'quit', 'exit'):
            raise SystemExit(0)
        if a.lower() == 'g':
            cfg.set('folder', folder)
            cfg.save()
            return folder
        if a.isdigit():
            if not 1 <= int(a) <= len(entries):
                say('Type a number from 1 to %d.' % len(entries))
                continue
            folder = os.path.abspath(entries[int(a) - 1])
            continue
        p = os.path.abspath(os.path.expanduser(a))
        if os.path.isdir(p):
            folder = p
        else:
            say('No such folder: ' + a)


def run_console(args, cfg):
    say('GetMssgPatCopies %s' % VERSION + ('' if args.console or args.yes else
                                           ' (no window: tkinter is not available here)'))
    if args.folder:
        folder = os.path.abspath(args.folder)
        if not os.path.isdir(folder):
            say('No such folder: ' + args.folder)
            return 2
        cfg.set('folder', folder)
        cfg.save()
    else:
        folder = console_pick_folder(cfg)
    try:
        job = Job(folder, year=args.year)
    except OSError as e:
        say('Cannot read %s: %s' % (folder, e))
        return 2
    existing = job.existing()
    if existing and not args.yes and not ask_yes_no('Already in %s: %s. Replace?' % (folder, ', '.join(existing))):
        say('Cancelled; nothing was saved.')
        return 1
    job.write()
    say()
    for line in job.summary():
        say(line)
    if job.files:
        say()
        say(job.details())
    return 0


# ---- Window mode (tkinter) ----

def run_gui(args, cfg):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import tkinter.font as tkfont

    MONO = ('Courier', 10)

    class App(tk.Tk):
        def __init__(self, cfg, start_folder=None):
            tk.Tk.__init__(self)
            self.cfg = cfg
            base = tkfont.nametofont('TkDefaultFont')
            self.title_font = base.copy()
            self.title_font.configure(weight='bold', size=abs(base.cget('size')) + 4)
            self.title('GetMssgPatCopies')
            if sys.platform.startswith('linux'):
                try:
                    ttk.Style().theme_use('clam')
                except tk.TclError:
                    pass
            self.minsize(760, 560)
            if cfg.get('geometry'):
                try:
                    self.geometry(cfg.get('geometry'))
                except tk.TclError:
                    pass
            self.protocol('WM_DELETE_WINDOW', self.close)
            self.folder = None
            self.entries = []       # (kind, full path) for each listbox line
            self.search = ''        # the USPTO line of the last run
            self.build()
            folder = start_folder or cfg.get('folder')
            self.open_folder(folder if folder and os.path.isdir(folder) else os.getcwd())

        # -- layout --
        def build(self):
            outer = ttk.Frame(self, padding=14)
            outer.pack(fill='both', expand=True)
            ttk.Label(outer, text='GetMssgPatCopies', font=self.title_font).pack(anchor='w')
            ttk.Label(outer, text='Open the folder with the patent copies and click Generate. Every copy that is '
                                  'zero bytes in size is listed in %s (Fetcher Format) and %s (for the USPTO '
                                  'Patent Public Search page), saved in that folder.' % (ORDER_NAME, USPTO_NAME),
                      wraplength=720, justify='left').pack(anchor='w', pady=(0, 10))

            box = ttk.LabelFrame(outer, text=' Folder with the patent copies ', padding=8)
            box.pack(fill='both', expand=True)
            row = ttk.Frame(box)
            row.pack(fill='x')
            ttk.Button(row, text='Choose folder...', command=self.choose_folder).pack(side='left')
            ttk.Button(row, text='Refresh', command=self.refresh).pack(side='left', padx=6)
            self.path_label = ttk.Label(box, text='', wraplength=700, justify='left', foreground='#555555')
            self.path_label.pack(anchor='w', pady=(6, 2))
            lb_frame = ttk.Frame(box)
            lb_frame.pack(fill='both', expand=True)
            self.listbox = tk.Listbox(lb_frame, height=12, exportselection=False, activestyle='none', font=MONO)
            # Folders are shown in dark blue on a pale blue band so they stand out from the files.
            self.folder_colours = {'foreground': '#1a4f9c', 'background': '#e8f0fb',
                                   'selectforeground': '#ffffff', 'selectbackground': '#1a4f9c'}
            bar = ttk.Scrollbar(lb_frame, orient='vertical', command=self.listbox.yview)
            self.listbox.configure(yscrollcommand=bar.set)
            bar.pack(side='right', fill='y')
            self.listbox.pack(side='left', fill='both', expand=True)
            self.listbox.bind('<<ListboxSelect>>', self.on_pick)
            self.listbox.bind('<Return>', self.on_pick)
            self.count_label = ttk.Label(box, text='', wraplength=700, justify='left')
            self.count_label.pack(anchor='w', pady=(6, 0))

            actions = ttk.Frame(outer)
            actions.pack(fill='x', pady=(12, 4))
            self.generate_btn = ttk.Button(actions, text='Generate', command=self.generate)
            self.generate_btn.pack(side='left')
            self.copy_btn = ttk.Button(actions, text='Copy USPTO search', command=self.copy_search)
            self.copy_btn.pack(side='left', padx=8)
            self.copy_btn.state(['disabled'])
            self.status = ttk.Label(outer, text='', wraplength=720, justify='left')
            self.status.pack(anchor='w')
            self.details = tk.Text(outer, height=8, font=MONO, wrap='char', state='disabled')
            self.details_bar = ttk.Scrollbar(outer, orient='vertical', command=self.details.yview)
            self.details.configure(yscrollcommand=self.details_bar.set)

        # -- folder browsing --
        def choose_folder(self):
            start = self.folder if self.folder else os.getcwd()
            chosen = filedialog.askdirectory(initialdir=start, title='Choose the folder with the patent copies',
                                             mustexist=True)
            if chosen:
                self.open_folder(chosen)

        def open_folder(self, folder):
            folder = os.path.abspath(folder)
            try:
                dirs, files = list_folder(folder)
            except OSError as e:
                self.set_status('Could not list folder: %s' % e, 'err')
                return
            if folder != self.folder:
                self.hide_details()
                self.set_status('')
                self.copy_btn.state(['disabled'])
            self.folder = folder
            self.cfg.set('folder', folder)
            self.cfg.save()
            self.path_label.configure(text=folder)
            self.listbox.delete(0, 'end')
            self.entries = []
            parent = os.path.dirname(folder)
            if parent != folder:
                self.entries.append(('up', parent))
                self.listbox.insert('end', '..  (up one level)')
                self.listbox.itemconfig('end', **self.folder_colours)
            for d in dirs:
                self.entries.append(('dir', os.path.join(folder, d)))
                self.listbox.insert('end', '[folder]  ' + d)
                self.listbox.itemconfig('end', **self.folder_colours)
            year = datetime.date.today().year
            for name, size in files:
                self.entries.append(('file', os.path.join(folder, name)))
                self.listbox.insert('end', '%-40s %12s' % (name, '{:,}'.format(size)))
                if size == 0 and canon_from_name(name, year):
                    self.listbox.itemconfig('end', foreground='#b3261e')
            if not dirs and not files:
                self.listbox.insert('end', '(empty folder)')
                self.listbox.itemconfig('end', foreground='#888888')
            r = survey(files, year)
            self.count_label.configure(
                text='%s here; %s named after a US number, %d of them zero bytes (shown in red).'
                     % (plural(len(files), 'file'), plural(r['copies'], 'file'),
                        sum(len(v) for v in r['files'].values()) + len(r['have_copy'])))

        def refresh(self):
            if self.folder:
                self.open_folder(self.folder)

        def on_pick(self, _event=None):
            sel = self.listbox.curselection()
            if not sel or sel[0] >= len(self.entries):
                return
            kind, full = self.entries[sel[0]]
            if kind != 'file':
                self.after_idle(lambda: self.open_folder(full))

        # -- results --
        def set_status(self, text, kind=''):
            colour = {'ok': '#1f7a3d', 'err': '#b3261e', 'warn': '#8a5a00'}.get(kind, '')
            self.status.configure(text=text, foreground=colour)

        def show_details(self, text):
            self.details.configure(state='normal')
            self.details.delete('1.0', 'end')
            self.details.insert('1.0', text)
            self.details.configure(state='disabled')
            self.details_bar.pack(side='right', fill='y')
            self.details.pack(fill='both', expand=True, pady=(6, 0))

        def hide_details(self):
            self.details.pack_forget()
            self.details_bar.pack_forget()

        def generate(self):
            self.hide_details()
            self.copy_btn.state(['disabled'])
            try:
                job = Job(self.folder)
                existing = job.existing()
                if existing and not messagebox.askyesno(
                        'Replace files?', 'Already in %s:\n\n%s\n\nReplace?' % (job.folder, '\n'.join(existing)),
                        parent=self):
                    self.set_status('Cancelled; nothing was saved.')
                    return
                job.write()
            except Exception as e:
                self.set_status('Error: %s' % e, 'err')
                return
            self.done_text = '\n'.join(job.summary())
            self.set_status(self.done_text, 'ok' if job.files else 'warn')
            if job.files:
                self.search = uspto_text(job.result['missing']).rstrip()
                self.copy_btn.state(['!disabled'])
                self.show_details(job.details())
            self.refresh()

        def copy_search(self):
            self.clipboard_clear()
            self.clipboard_append(self.search)
            self.set_status(self.done_text + '\nCopied the USPTO search; paste it into the Patent Public Search box.',
                            'ok')

        def close(self):
            try:
                self.cfg.set('geometry', self.geometry())
                self.cfg.save()
            finally:
                self.destroy()

    start_folder = os.path.abspath(args.folder) if args.folder else None
    if start_folder and not os.path.isdir(start_folder):
        raise SystemExit('No such folder: ' + args.folder)
    app = App(cfg, start_folder)
    app.mainloop()
    return 0


def gui_possible():
    """True when tkinter imports and can open a window (a display exists)."""
    try:
        import tkinter as tk
    except ImportError:
        return False
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


def parse_args(argv):
    p = argparse.ArgumentParser(prog='GetMssgPatCopies', description=DESCRIPTION,
                                epilog='Without --yes the program asks its questions, in a window when tkinter '
                                       'is available or in the terminal otherwise.')
    p.add_argument('folder', nargs='?', help='the folder with the patent copies')
    p.add_argument('--yes', '-y', action='store_true',
                   help='ask nothing: generate the lists for FOLDER and replace existing ones')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--console', action='store_true', help='work in the terminal even if a window is possible')
    g.add_argument('--gui', action='store_true', help='open the window (the default when possible)')
    p.add_argument('--year', type=int, help=argparse.SUPPRESS)
    p.add_argument('--version', action='version', version='GetMssgPatCopies ' + VERSION)
    args = p.parse_args(argv)
    if args.yes and not args.folder:
        p.error('--yes needs the folder')
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    cfg = Config()
    if args.yes:
        return run_console(args, cfg)
    if not args.console and gui_possible():
        return run_gui(args, cfg)
    if sys.stdout is None or sys.stdin is None:
        # Started with pythonw and no window could be opened: there is nowhere to ask.
        if sys.stderr is not None:
            sys.stderr.write('GetMssgPatCopies could not open a window and has no terminal to ask in; '
                             'run it from a command prompt, or give the folder and --yes.\n')
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, 'GetMssgPatCopies could not open a window (tkinter is missing). '
                                                'Run it from a command prompt instead.', 'GetMssgPatCopies', 0x10)
        except Exception:
            pass
        return 1
    return run_console(args, cfg)


if __name__ == '__main__':
    sys.exit(main())
