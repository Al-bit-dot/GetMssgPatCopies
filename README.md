# GetMssgPatCopies

GetMssgPatCopies looks in a folder of patent copies for the ones that are **zero bytes** in size
(the copies that did not come through) and writes their numbers into two files in that same folder,
so they can be fetched again:

| File | Contents |
|---|---|
| `MssgPat-Order.txt` | Fetcher Format: one number per line, Windows line endings, in the standard form PatCopyPrint uses (`01234567`, `20120001234`, `D0512345`) |
| `MssgPat-USPTO-Order.txt` | One line to paste into the [USPTO Patent Public Search](https://ppubs.uspto.gov/pubwebapp/) box: `("1234567" or "20120001234" or "D512345").pn.` |

Both lists are in the same order, the sorted order of PatCopyPrint and RemoveDupNumbers: patents by
number, then published applications by number, then D, H, PP, RE and the other letter prefixes.

![The GetMssgPatCopies window after Generate](docs/window.png)

It is one Python program, `GetMssgPatCopies.py`, that runs anywhere PatCopyPrint runs (Windows 7,
Windows 11, Ubuntu 14.10 with Python 3.4, Fedora) and needs only Python's own library. It opens a
window when tkinter is available and otherwise works in the terminal. Nothing is sent anywhere.

## Starting it

- **Windows:** put `GetMssgPatCopies.py` and `GetMssgPatCopies.pyw` in the same folder and
  double-click **`GetMssgPatCopies.pyw`** (no black console window).
- **Linux:** `python3 GetMssgPatCopies.py`.
- `python3 GetMssgPatCopies.py --console` uses the terminal even when a window is possible, and
  `python3 GetMssgPatCopies.py FOLDER --yes` writes the two files for FOLDER without asking anything.

Installing Python (also offline) is described in the
[PatCopyPrint README](https://github.com/Al-bit-dot/PatCopyPrint#installing-python-on-a-computer-with-no-internet);
GetMssgPatCopies needs the same Python and nothing more.

The last folder is remembered in `.getmssgpatcopies.json` in your home folder.

## Using the window

1. Pick the folder as in PatCopyPrint: **Choose folder…** opens one, and the list shows its
   sub-folders (in blue) and its files with their sizes. Click a folder line or `..` to move
   around. The folder whose contents are shown is the one that will be read. Zero-byte patent
   copies are shown in red.
2. Click **Generate**. If the two files are already in the folder you are asked once before they
   are replaced. The result is shown below the button with the numbers found and the USPTO line.
3. **Copy USPTO search** puts the USPTO line on the clipboard. On the Patent Public Search page
   close the *Notification* pop-up, paste the line into the search box and search.

## Using the terminal

The program lists the sub-folders of the remembered folder. Type a number to open a folder, a
path to go somewhere else, `g` (or just Enter) to generate the files for the folder shown, or `q`
to quit.

## Which files count

Only the files directly in the chosen folder are read (not its sub-folders). A file counts as a
patent copy when its name without the extension is a US number in any of these spellings:

| Kind | File names recognised | Fetcher list | USPTO line |
|---|---|---|---|
| Utility patent | `09123456.pdf`, `9123456.pdf`, `US9123456B2.pdf`, `US-9123456-B2.pdf` | `09123456` | `"9123456"` |
| Published application | `20120001234.pdf`, `2012001234.pdf`, `US20120001234A1.pdf` | `20120001234` | `"20120001234"` |
| Design, H, T, X | `D0512345.pdf`, `USD512345S.pdf` | `D0512345` | `"D512345"` |
| RE, RD, RX, AI, PP | `RE045678.pdf`, `USRE45678E.pdf`, `USPP12345P2.pdf` | `RE045678`, `PP012345` | `"RE45678"`, `"PP12345"` |

- A number is listed once, even when several zero-byte files have it (`9123456.pdf` and
  `09123456.pdf`).
- A number is **not** listed when another file of the same number in the folder has content
  (`06111222.pdf` is empty but `US6111222B1.pdf` is the real copy). The result names those files.
- Zero-byte files whose names are not US numbers (`notes.txt`, `WO2010123456.pdf`) are left out
  and named in the result.
- If no patent copy is zero bytes, nothing is written.

The numbers in the USPTO line follow the Patent Public Search rule for patent numbers: seven
characters, with leading zeros where needed and a letter prefix counting towards the seven
(`D512345`, `RE45678`, `PP12345`); patents with eight digits and published applications (11 digits)
are written in full. The line ends with `.pn.` (with the final period) so that the search finds
the documents themselves, not the documents that cite them.

## Tests

`python3 test_getmssgpatcopies.py` checks the file-name rules, the sort order, the two file
formats, a run over a sample folder and the command line.
