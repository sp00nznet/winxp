#!/usr/bin/env python3
"""A private Windows 2000 profile for a lifted shell, so it never walks the
host's (the host's Start Menu, Desktop and their programs' icons).

    py -3 tools/profile.py BOX DIR      (e.g. w2k\\explorer work/profile)

Makes DIR/user and DIR/all with Windows 2000's folder names, and writes the
shell folder values (User Shell Folders as %USERPROFILE%/%ALLUSERSPROFILE%
paths, Shell Folders expanded) into the box under
HKCU\\Software\\pcrecomp\\BOX\\{HKCU,HKLM}: the box answers a value before the
real key (pcrecomp regbox32.c). The runner points USERPROFILE and
ALLUSERSPROFILE at DIR/user and DIR/all (tools/run_explorer.sh).
Also Windows 2000's own colour scheme (HIVEDEF.INF's HKCU Control Panel\\Colors,
from work/iso/I386): the emulated win32k takes the box's colours (pcrecomp w32kuser.c).
ponytail: Windows 2000's names only; a host-only value (a GUID-named folder)
still falls through to the host's key, which Windows 2000's shell32 never asks for.
"""
import os, re, sys, winreg

USER = {'AppData': r'Application Data', 'Cookies': 'Cookies', 'Desktop': 'Desktop', 'Favorites': 'Favorites',
        'NetHood': 'NetHood', 'Personal': 'My Documents', 'My Pictures': r'My Documents\My Pictures',
        'PrintHood': 'PrintHood', 'Recent': 'Recent', 'SendTo': 'SendTo', 'Start Menu': 'Start Menu',
        'Programs': r'Start Menu\Programs', 'Startup': r'Start Menu\Programs\Startup', 'Templates': 'Templates',
        'Local Settings': 'Local Settings', 'Local AppData': r'Local Settings\Application Data',
        'History': r'Local Settings\History', 'Cache': r'Local Settings\Temporary Internet Files'}
COMMON = {'Common Desktop': 'Desktop', 'Common Start Menu': 'Start Menu', 'Common Programs': r'Start Menu\Programs',
          'Common Startup': r'Start Menu\Programs\Startup', 'Common Documents': 'Documents',
          'Common AppData': 'Application Data', 'Common Favorites': 'Favorites', 'Common Templates': 'Templates'}
EXP = r'Software\Microsoft\Windows\CurrentVersion\Explorer'

def seed(box, hive, var, base, folders, guest):
    root = r'Software\pcrecomp\%s\%s\%s' % (box, hive, EXP)
    for key, kind, fmt in (('User Shell Folders', winreg.REG_EXPAND_SZ, '%%%s%%\\%s'), ('Shell Folders', winreg.REG_SZ, None)):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root + '\\' + key) as k:
            clear(k)    # answered whole (regbox32 os_owned_key): Windows 2000's names only, no host leftovers
            for name, rel in folders.items():
                winreg.SetValueEx(k, name, 0, kind, fmt % (var, rel) if fmt else guest + '\\' + rel)
    for rel in folders.values() if base else ():
        os.makedirs(os.path.join(base, rel), exist_ok=True)

def clear(k):
    while True:
        try: winreg.DeleteValue(k, winreg.EnumValue(k, 0)[0])
        except OSError: return

# The keys pcrecomp's regbox32 answers from the box only (os_owned_key), seeded from
# Windows 2000's own INFs: HKCU Environment and Policies (HIVEDEF), Session Manager\Environment (HIVESYS)
OWNED = re.compile(r'(?i)^(HKCU,"(Environment|Software\\Microsoft\\Windows\\CurrentVersion\\(Explorer|Policies))'
                   r'|HKLM,"(SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment'
                   r'|SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies))[\\"]')

def owned(box, infdir, guest):
    """Each single-line string/dword value of the OS-owned keys, plus what Windows 2000's userenv
    makes at logon (ProfileList's directories, Volatile Environment), for the profile at GUEST.
    ponytail: no per-SID ProfileList entry (the token's SID is the host's), no LOGONSERVER."""
    for inf in ('HIVEDEF.INF', 'HIVESYS.INF', 'HIVESFT.INF'):
        f = os.path.join(infdir, inf)
        if not os.path.exists(f):
            continue
        lines = open(f, encoding='latin-1').read().splitlines()
        strs = dict(re.findall(r'^(\w+)\s*=\s*"?(.*?)"?\s*$', '\n'.join(lines[[l.strip().lower() for l in lines].index('[strings]'):]), re.M)) \
            if '[strings]' in [l.strip().lower() for l in lines] else {}
        for l in lines:
            # (the shell folders are seed()'s, matching the folders it makes: HIVEDEF's History is
            # %USERPROFILE%\History, which Windows 2000's userenv moves under Local Settings)
            if not OWNED.match(l) or l.rstrip().endswith('\\') or 'Shell Folders"' in l:
                continue
            m = re.match(r'(HKCU|HKLM),"([^"]+)",(?:"([^"]*)")?,?(0x[0-9a-fA-F]+)?,?(.*)$', l.strip())
            if not m:
                continue
            hive, key, name, fl, data = m.groups()
            fl = int(fl or '0', 16)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\pcrecomp\%s\%s\%s' % (box, hive, key)) as k:
                if name is None or fl & 0x10:
                    continue
                data = re.sub(r'%(\w+)%', lambda x: strs.get(x.group(1), x.group(0)), data.strip().strip('"'))
                if fl & 0x10001 == 0x10001:
                    winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(data, 0))
                elif fl & 0x10000 == 0:
                    winreg.SetValueEx(k, name, 0, winreg.REG_EXPAND_SZ if fl & 0x20000 else winreg.REG_SZ, data)
    nt = r'Software\pcrecomp\%s\HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' % box
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, nt) as k:
        clear(k)
        winreg.SetValueEx(k, 'ProfilesDirectory', 0, winreg.REG_EXPAND_SZ, guest.replace('C:', '%SystemDrive%', 1))
        winreg.SetValueEx(k, 'AllUsersProfile', 0, winreg.REG_SZ, 'all')
        winreg.SetValueEx(k, 'DefaultUserProfile', 0, winreg.REG_SZ, 'Default User')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\pcrecomp\%s\HKCU\Volatile Environment' % box) as k:
        clear(k)
        if guest[1:2] == ':':
            winreg.SetValueEx(k, 'HOMEDRIVE', 0, winreg.REG_SZ, guest[:2])
            winreg.SetValueEx(k, 'HOMEPATH', 0, winreg.REG_SZ, guest[2:] + r'\user')
        winreg.SetValueEx(k, 'APPDATA', 0, winreg.REG_SZ, guest + r'\user\Application Data')

def colors(box, inf):
    """HKCU,"Control Panel\\Colors","Background",0x00000000,"58 110 165" lines into the box"""
    if not os.path.exists(inf):
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\pcrecomp\%s\HKCU\Control Panel\Colors' % box) as k:
        for l in open(inf, encoding='latin-1'):
            m = re.match(r'HKCU,"Control Panel\\Colors","(\w+)",0x0000000[02],"([\d ]+)"', l)
            if m:
                winreg.SetValueEx(k, m.group(1), 0, winreg.REG_SZ, m.group(2))

ACCESSORIES = [('Notepad', 'notepad.exe'), ('Calculator', 'calc.exe'), ('Paint', 'mspaint.exe'), ('WordPad', 'wordpad.exe'),
               (r'Games\FreeCell', 'freecell.exe'), (r'Games\Minesweeper', 'winmine.exe'), (r'Games\Solitaire', 'sol.exe')]

def lnk(path, guest):
    """A Windows 2000 shortcut to a guest file, as Windows 2000's setup writes the Accessories ones:
    the target as an expandable string (%SystemRoot%\\system32\\x.exe, an EXP_SZ block) and the
    working directory %HOMEDRIVE%%HOMEPATH%. shell32 makes the target's ID list itself when it loads
    the link (an ID list built here was not one CShellLink could invoke). No LinkInfo: linkinfo.dll is
    not in the guest. ponytail: no dates, sizes or icon location."""
    import struct
    target = guest.replace('C:\\WINNT', '%SystemRoot%', 1)
    flags = 0x10 | 0x80 | 0x200                       # SLDF_HAS_WORKINGDIR | SLDF_UNICODE | SLDF_HAS_EXP_SZ
    hdr = struct.pack('<I16sIIQQQIIIHHII', 0x4C, bytes.fromhex('0114020000000000C000000000000046'), flags, 0x20, 0, 0, 0,
                      0, 0, 1, 0, 0, 0, 0)
    wd = '%HOMEDRIVE%%HOMEPATH%'
    strings = struct.pack('<H', len(wd)) + wd.encode('utf-16le')
    a, w = target.encode('mbcs' if os.name == 'nt' else 'latin-1'), target.encode('utf-16le')
    exp = struct.pack('<II', 0x314, 0xA0000001) + a.ljust(260, b'\0')[:260] + w.ljust(520, b'\0')[:520]
    with open(path, 'wb') as f:
        f.write(hdr + strings + exp + b'\0\0\0\0')

def accessories(d, sysdir):
    """All Users' Start Menu\\Programs\\Accessories (Windows 2000's names) to the lifted accessories:
    the targets are Windows 2000's own files in the box's C:\\WINNT\\system32, for their icons only;
    the launch path starts the lifted runner by name (win2000 src/nthost.c), never the file."""
    import shutil
    box_sys = os.path.join(d, '..', 'WINNT', 'system32')
    os.makedirs(box_sys, exist_ok=True)
    for name, exe in ACCESSORIES:
        src = os.path.join(sysdir, exe)
        if os.path.exists(src) and not os.path.exists(os.path.join(box_sys, exe)):
            shutil.copyfile(src, os.path.join(box_sys, exe))
        p = os.path.join(d, 'all', 'Start Menu', 'Programs', 'Accessories', name + '.lnk')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        lnk(p, 'C:\\WINNT\\system32\\' + exe)

if __name__ == '__main__':
    # DIR '-': the registry only, no folders (a stage 1 app: no file box, so nothing is made on the host;
    # its folders name Windows 2000's C:\Documents and Settings, GUEST)
    box, d = sys.argv[1], None if sys.argv[2] == '-' else os.path.abspath(sys.argv[2])
    g = sys.argv[3] if len(sys.argv) > 3 else d     # the guest's name for DIR (in a file box: C:\...)
    inf = os.path.join(os.path.dirname(__file__), '..', 'work', 'iso', 'I386')
    seed(box, 'HKCU', 'USERPROFILE', d and os.path.join(d, 'user'), USER, g + r'\user')
    seed(box, 'HKLM', 'ALLUSERSPROFILE', d and os.path.join(d, 'all'), COMMON, g + r'\all')
    owned(box, inf, g)
    if d:
        colors(box, os.path.join(inf, 'HIVEDEF.INF'))
    if d and g.startswith('C:\\'):     # in a file box: DIR is the box's C:\Documents and Settings
        accessories(d, os.path.join(os.path.dirname(__file__), '..', 'work', 'sys'))
    print('profile %s: %s' % (box, d or g))
