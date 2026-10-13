#!/usr/bin/env python3
"""Tests for GetMssgPatCopies.py:  python3 test_getmssgpatcopies.py"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import GetMssgPatCopies as g

YEAR = 2026


class Names(unittest.TestCase):
    def test_patent_copy_names(self):
        cases = {
            '09123456.pdf': '09123456',
            '9123456.pdf': '09123456',
            '10123456.pdf': '10123456',
            '00012345.PDF': '00012345',
            'US9123456B2.pdf': '09123456',
            'us 9123456 b2.pdf': '09123456',
            'US-9123456-B2.pdf': '09123456',
            '20020123457.pdf': '20020123457',
            '2002123457.pdf': '20020123457',
            'US20020123457A1.pdf': '20020123457',
            'D0512345.pdf': 'D0512345',
            'USD512345S.pdf': 'D0512345',
            'RE045678.pdf': 'RE045678',
            'USRE45678E.pdf': 'RE045678',
            'PP012345.pdf': 'PP012345',
            'USPP12345P2.pdf': 'PP012345',
            'H0001234.pdf': 'H0001234',
            '09123456': '09123456',
        }
        for name, canon in cases.items():
            self.assertEqual(g.canon_from_name(name, YEAR), canon, name)

    def test_not_patent_copies(self):
        for name in ('notes.txt', 'MssgPat-Order.txt', 'WO2010123456.pdf', 'EP1234567B1.pdf',
                     '00000000.pdf', '123456789.pdf', '20990123456.pdf', '19990123456.pdf',
                     '20020000000.pdf', 'D12345678.pdf', 'RE1234567.pdf', 'ZZ123456.pdf',
                     '09123456 (1).pdf', 'Fig1.pdf', '.pdf'):
            self.assertIsNone(g.canon_from_name(name, YEAR), name)


class Formats(unittest.TestCase):
    def test_sort_order(self):
        # Patents by number, then published applications, then prefixed documents
        # (PatCopyPrint "Sorted" and RemoveDupNumbers give this same order).
        mixed = ['RE045678', '20240123457', 'D0512345', '10123456', '09123456', '20020123457',
                 '00012345', 'H0001234', 'PP012345']
        self.assertEqual(g.sort_canons(mixed),
                         ['00012345', '09123456', '10123456', '20020123457', '20240123457',
                          'D0512345', 'H0001234', 'PP012345', 'RE045678'])

    def test_uspto_numbers(self):
        cases = {'09123456': '9123456', '01234567': '1234567', '10123456': '10123456',
                 '00012345': '0012345', '20120001234': '20120001234', 'D0512345': 'D512345',
                 'D0000126': 'D000126', 'RE045678': 'RE45678', 'PP012345': 'PP12345',
                 'H0001234': 'H001234'}
        for canon, shown in cases.items():
            self.assertEqual(g.uspto_number(canon), shown, canon)

    def test_files_text(self):
        self.assertEqual(g.order_text(['01234567', '20120001234']), '01234567\r\n20120001234\r\n')
        self.assertEqual(g.uspto_text(['01234567', '20120001234']), '("1234567" or "20120001234").pn.\r\n')
        self.assertEqual(g.uspto_text(['01234567']), '("1234567").pn.\r\n')


class Folder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        files = {
            '20120001234.pdf': 0,
            '01234567.pdf': 0,
            'D0512345.pdf': 0,
            '07000001.pdf': 5000,        # downloaded fine
            '06111222.pdf': 0,            # zero bytes ...
            'US6111222B1.pdf': 7000,      # ... but another copy of the same number has content
            'US20190012345A1.pdf': 0,
            'notes.txt': 0,               # zero bytes, not a patent copy
            'WO2010123456.pdf': 0,        # not a US number
        }
        for name, size in files.items():
            with open(os.path.join(self.dir, name), 'wb') as f:
                f.write(b'x' * size)
        os.mkdir(os.path.join(self.dir, '09999999.pdf'))   # a folder is not a copy

    def tearDown(self):
        shutil.rmtree(self.dir)

    def read(self, name):
        with open(os.path.join(self.dir, name), 'rb') as f:
            return f.read()

    def test_job(self):
        job = g.Job(self.dir, year=YEAR)
        r = job.result
        self.assertEqual(r['missing'], ['01234567', '20120001234', '20190012345', 'D0512345'])
        self.assertEqual(r['have_copy'], ['06111222.pdf'])
        self.assertEqual(r['not_patents'], ['WO2010123456.pdf', 'notes.txt'])
        self.assertEqual(r['files']['20190012345'], ['US20190012345A1.pdf'])
        self.assertEqual(job.existing(), [])
        job.write()
        self.assertEqual(self.read(g.ORDER_NAME), b'01234567\r\n20120001234\r\n20190012345\r\nD0512345\r\n')
        self.assertEqual(self.read(g.USPTO_NAME),
                         b'("1234567" or "20120001234" or "20190012345" or "D512345").pn.\r\n')
        self.assertEqual(sorted(g.Job(self.dir, year=YEAR).existing()), sorted([g.ORDER_NAME, g.USPTO_NAME]))

    def test_nothing_missing(self):
        for name in os.listdir(self.dir):
            if name.endswith('.pdf') and os.path.isfile(os.path.join(self.dir, name)):
                os.remove(os.path.join(self.dir, name))
        with open(os.path.join(self.dir, '01234567.pdf'), 'wb') as f:
            f.write(b'%PDF')
        job = g.Job(self.dir, year=YEAR)
        self.assertEqual(job.files, [])
        self.assertIn('nothing was saved', job.summary()[0])

    def test_command_line(self):
        env = dict(os.environ, HOME=self.dir, USERPROFILE=self.dir)
        out = subprocess.check_output([sys.executable, os.path.join(HERE, 'GetMssgPatCopies.py'),
                                       self.dir, '--yes', '--year', str(YEAR)],
                                      env=env, universal_newlines=True)
        self.assertIn('4 numbers with a zero-byte copy', out)
        self.assertIn('("1234567" or "20120001234" or "20190012345" or "D512345").pn.', out)
        self.assertTrue(os.path.exists(os.path.join(self.dir, g.ORDER_NAME)))


if __name__ == '__main__':
    unittest.main()
