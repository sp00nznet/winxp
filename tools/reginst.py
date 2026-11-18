#!/usr/bin/env python3
"""Seed a lifted program's registry box with Windows 2000's own COM classes.

    py -3 tools/reginst.py BOX DIR DLL...    (e.g. w2k\\explorer work/rebased-shell browseui shell32)

Each DLL's REGINST resource (the INF its DllRegisterServer hands to advpack)
is read, and its HKCR CLSID\\ and AppID\\ lines are written under
HKCU\\Software\\pcrecomp\\BOX\\HKLM\\SOFTWARE\\Classes: with a lifted ole32
only the box answers those keys (pcrecomp regbox32.c), never the host's.
The server path (%_SYS_MOD_PATH%) is the DLL in DIR, a lifted module's name.
Also the INFs' HKLM ...\\NameSpace lines (the desktop's and My Computer's items).
ponytail: the other HKLM extras (approved shell extensions,
ShellCompatibility) are left out until something asks for them.
"""
import csv, os, re, sys, winreg
import pefile
# the guest's system32 (its SystemRoot is the host's name, C:\Windows): in the file box, the lifted modules
SYS32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')

def reginst(path):
    p = pefile.PE(path, fast_load=True)
    p.parse_data_directories([pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
    for t in getattr(p, 'DIRECTORY_ENTRY_RESOURCE', type('', (), {'entries': []})).entries:
        if t.name and str(t.name) == 'REGINST':
            e = t.directory.entries[0].directory.entries[0].data.struct
            return p.get_data(e.OffsetToData, e.Size).decode('latin-1')
    return ''

def lines(inf, mod):
    sec, strs = {}, {'_SYS_MOD_PATH': mod, '_MOD_PATH': mod}
    if mod: strs['11'] = os.path.dirname(mod)   # LDID 11, the system directory (LocalizedString's @%11%\shell32.dll,-8964): the lifted modules' own
    cur = None
    for l in re.sub(r'\\[ \t]*\r?\n\s*', '', inf).splitlines():   # INF line continuations
        l = l.split(';')[0].strip() if not l.strip().startswith('"') else l.strip()
        if l.startswith('['): cur = sec.setdefault(l[1:l.index(']')].lower(), [])
        elif l and cur is not None: cur.append(l)
    for l in sec.get('strings', []):
        m = re.match(r'(\w+)\s*=\s*"?(.*?)"?$', l)
        if m: strs[m.group(1)] = m.group(2)
    sub = lambda s: re.sub(r'%(\w+)%', lambda m: strs.get(m.group(1), m.group(0)), s)
    for l in [x for k, v in sec.items() if k != 'strings' and 'del' not in k for x in v]:
        f = [x.strip() for x in next(csv.reader([sub(l)], skipinitialspace=True))]
        if len(f) >= 2 and f[0].upper() == 'HKCR' and re.match(r'(CLSID|AppID)\\|(Folder|Directory|Drive|lnkfile|\.lnk|exefile|\.exe)(\\|$)', f[1], re.I):
            yield f + [''] * (5 - len(f))
        # the shell's namespaces (Desktop, MyComputer, ...\NameSpace): with the box's own key the
        # host's is never enumerated (Win11's 33 desktop items were nameless folders on the desktop)
        elif len(f) >= 2 and f[0].upper() == 'HKLM' and re.search(r'\\NameSpace\\', f[1], re.I):
            yield f + [''] * (5 - len(f))
        # the time zones (Date/Time's list and its current zone's name): Windows 2000's, the box's
        # whole (pcrecomp regbox32.c; Windows 11's Display values are @tzres.dll MUI strings).
        # ponytail: IndexMapping (a multi-string) left out
        elif len(f) >= 3 and f[0].upper() == 'HKLM' and re.search(r'\\Time Zones', f[1], re.I) and f[2] != 'IndexMapping':
            yield f + [''] * (5 - len(f))

def hive_items(iso, dlls):
    """HIVESFT's Desktop\\NameSpace items served by one of DLLS, and HIVECLS's lines for those
    classes (Recycle Bin is shell32's, but HIVECLS registers it, not shell32's REGINST)."""
    rd = lambda f: open(os.path.join(iso, f), encoding='latin-1').read() if os.path.exists(os.path.join(iso, f)) else ''
    cls = list(lines(rd('HIVECLS.INF'), ''))
    srv = {x[1].split('\\')[1].upper(): x[4].lower() for x in cls
           if x[1].upper().endswith('\\INPROCSERVER32') and not x[2]}
    ns = [x for x in lines(rd('HIVESFT.INF'), '') if re.search(r'Desktop\\NameSpace\\\{.*\}$', x[1], re.I)
          and srv.get(x[1].rsplit('\\', 1)[1].upper(), '').replace('.dll', '') in dlls]
    want = {x[1].rsplit('\\', 1)[1].upper() for x in ns}
    # every HIVECLS class a lifted DLL serves (the shell link, {00021401}: shell32's, registered there)
    want |= {c for c, s in srv.items() if s.replace('.dll', '') in dlls}
    # and the shell's own classes: a folder's open verb is Windows 2000's "Explorer.exe /idlist,%I,%L"
    # (the host's Folder\shell\open has no arguments: every folder opened as My Documents)
    # and shortcuts and programs (lnkfile's link handler): the box answers a class it has whole (pcrecomp regbox32.c)
    shell = [x for x in cls if x[1].split('\\')[0].upper() in ('FOLDER', 'DIRECTORY', 'DRIVE', 'LNKFILE', '.LNK', 'EXEFILE', '.EXE')]
    tz = [x for x in lines(rd('HIVESFT.INF'), '') if re.search(r'\\Time Zones', x[1], re.I)]
    return ns + tz + [x for x in cls if '\\' in x[1] and x[1].split('\\')[1].upper() in want] + shell

def main():
    box, d, dlls = sys.argv[1], sys.argv[2], sys.argv[3:]
    root = r'Software\pcrecomp\%s\HKLM\SOFTWARE\Classes' % box
    n = 0
    for dll in dlls:
        f = os.path.abspath(os.path.join(d, dll if '.' in dll else dll + '.dll'))
        items = list(lines(reginst(f), f))
        if dll == dlls[-1]:
            items += hive_items(os.path.join(os.path.dirname(__file__), '..', 'work', 'iso', 'I386'), [x.lower() for x in dlls])
        for hive, key, name, flags, val, *data in items:
            if flags and not re.match(r'(?i)^(0x)?[0-9a-f]+$', flags): flags, val = '', flags   # mydocs: HKLM,key,,"My Documents" (no flags field)
            fl = int(flags, 0) if flags else 0
            # %SystemRoot%\System32\x.dll or a bare x.dll is the lifted module in DIR, never the host's:
            # named as the guest's system32 file, which the file box (pcrecomp syscall32.c) serves from DIR
            val = re.sub(r'(?i)^(%SystemRoot%\\System32\\)?(\w+\.dll)',
                         lambda m: os.path.join(SYS32, m.group(2)), val)
            # so is a file in an INF directory (LDID 10/25 Windows, 11 System32): My Computer's %25%\Explorer.exe,0
            val = re.sub(r'(?i)^%(?:10|11|25|SystemRoot)%\\(\w+\.(?:dll|exe))',
                         lambda m: os.path.join(SYS32, m.group(1).lower()), val)
            at = root if hive.upper() == 'HKCR' else r'Software\pcrecomp\%s\HKLM' % box
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, at + '\\' + key) as k:
                if fl & 1 and fl >> 16 == 3:                     # REG_BINARY, its bytes across the fields
                    winreg.SetValueEx(k, name or None, 0, winreg.REG_BINARY, bytes(int(x, 16) for x in [val] + data if x))
                elif fl & 1 and fl & 0x10000: winreg.SetValueEx(k, name or None, 0, winreg.REG_DWORD, int(val or '0', 0))
                elif not (fl & 0xFFFF0000 == 0 and fl & 2 and val == '' and not name):   # a named empty value is data (lnkfile's IsShortcut)
                    winreg.SetValueEx(k, name or None, 0, winreg.REG_EXPAND_SZ if fl & 0x20000 else winreg.REG_SZ, val)
            n += 1
    print('%d class lines into HKCU\\%s' % (n, root))
    # My Computer's namespace is the box's (none of Windows 2000's items there is served by a lifted
    # DLL): the host's (Win11's 3D Objects, Downloads, ...) were 11 nameless folders next to C:
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\pcrecomp\%s\HKLM\SOFTWARE\Microsoft\Windows'
                     r'\CurrentVersion\Explorer\MyComputer\NameSpace' % box).Close()
    hklm = r'Software\pcrecomp\%s\HKLM\SOFTWARE' % box
    cv = hklm + r'\Microsoft\Windows\CurrentVersion'
    # Control Panel's namespace too (the host's two Win11 items were nameless folders)
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, cv + r'\Explorer\ControlPanel\NameSpace').Close()
    # shell32 lists two Control Panel items of its own (required regitems, CLSIDs in its code):
    # Scheduled Tasks (mstask.dll) and Network and Dial-up Connections (netshell.dll). Neither
    # server is lifted (both reach host services), so their CLSIDs have no name: two nameless
    # folders. Windows 2000's own way to keep a regitem out of a listing: ShellFolder Attributes
    # with SFGAO_NONENUMERATED. ponytail: lift mstask/netshell and drop these to show them.
    for clsid in ('{D6277990-4C6A-11CF-8D87-00AA0060F5BF}', '{7007ACC7-3202-11D1-AAD2-00805FC1270E}'):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root + r'\CLSID\%s\ShellFolder' % clsid) as k:
            winreg.SetValueEx(k, 'Attributes', 0, winreg.REG_DWORD, 0x00100000)
    # The Internet Explorer desktop item's icon (IE's setup writes it on Windows 2000; no INF has it):
    # iexplore.exe as a file in the box's Program Files (run_explorer.sh), never run
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root + r'\CLSID\{871C5380-42A0-1069-A2EA-08002B30309D}\DefaultIcon') as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, r'C:\Program Files\Internet Explorer\IEXPLORE.EXE,-32528')
    # The applets Control Panel lists: the guest's system32 cannot be listed (the file box), so
    # the CPLs key names them (shell32 reads it as well as *.CPL); InProcCPLs runs each inside
    # explorer (Control_RunDLL in process), not through rundll32: no runner for it
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cv + r'\Control Panel\CPLs') as k, \
         winreg.CreateKey(winreg.HKEY_CURRENT_USER, cv + r'\Explorer\ControlPanel\InProcCPLs') as ip:
        for cpl in ('timedate.cpl', 'desk.cpl', 'main.cpl'):
            winreg.SetValueEx(k, cpl.split('.')[0], 0, winreg.REG_SZ, os.path.join(SYS32, cpl))
            winreg.SetValueEx(ip, cpl, 0, winreg.REG_SZ, '')
    # Windows 2000's mpr.dll (main.cpl imports it) loads the network providers named here: the
    # host's (ntlanman, RDPNP, P9NP) are host DLLs, so none
    for order in ('Order', 'HwOrder'):   # (mpr reads both)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\pcrecomp\%s\HKLM\SYSTEM\CurrentControlSet'
                              r'\Control\NetworkProvider\%s' % (box, order)) as k:
            winreg.SetValueEx(k, 'ProviderOrder', 0, winreg.REG_SZ, '')
    # The URL protocols' icons, which url.dll's registration code (no INF) writes on Windows 2000:
    # the folder window's frame reads HKCR\http\DefaultIcon into a buffer it never checks
    # (shdocvw sub_20E12126), so a missing key is an uninitialized path into Shell_GetCachedImageIndex
    for proto in ('http', 'https', 'ftp'):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root + '\\' + proto + r'\DefaultIcon') as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, os.path.join(SYS32, 'url.dll') + ',0')
    # App Paths for each lifted program's runner (build\nt<name>.exe): the Run dialog's
    # "winmine" resolves there, and the host's launch guard starts only those
    b = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build'))
    ap = r'Software\pcrecomp\%s\HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths' % box
    for f in os.listdir(b):
        if re.match(r'nt\w+\.exe$', f) and f != 'ntexplorer.exe':
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ap + '\\' + f[2:]) as k:
                winreg.SetValueEx(k, None, 0, winreg.REG_SZ, os.path.join(SYS32, f))   # the guest's name: the file box serves it from build

if __name__ == '__main__':
    main()
