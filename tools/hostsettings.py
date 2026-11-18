#!/usr/bin/env python3
"""The host's live settings a Control Panel applet could change, one per line.

    py -3 tools/hostsettings.py > work/regsnap/host_before.txt   (and after; diff them)

Clock: the boot time (now - uptime) to the second, so a set of the system time
shows as a jump; the time zone; the display mode; SystemParametersInfo GETs
for the mouse, keyboard, desktop and screen saver; the double-click time,
swapped buttons, caret blink rate and the cursor scheme in the registry.
"""
import ctypes
import ctypes.wintypes as W
import datetime
import time
import winreg

u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
k32.GetTickCount64.restype = ctypes.c_ulonglong

boot = time.time() - k32.GetTickCount64() / 1000.0
print('boot time (now - uptime): %s' % datetime.datetime.fromtimestamp(round(boot / 2) * 2))


class TZI(ctypes.Structure):
    _fields_ = [('Bias', W.LONG), ('StandardName', W.WCHAR * 32), ('s', W.WORD * 8), ('StandardBias', W.LONG),
                ('DaylightName', W.WCHAR * 32), ('d', W.WORD * 8), ('DaylightBias', W.LONG)]


tz = TZI()
k32.GetTimeZoneInformation(ctypes.byref(tz))
print('time zone: bias %d %s' % (tz.Bias, tz.StandardName))


class DEVMODEW(ctypes.Structure):
    _fields_ = [('dmDeviceName', W.WCHAR * 32), ('a', W.WORD * 4), ('dmFields', W.DWORD), ('pos', W.LONG * 2),
                ('o', W.DWORD * 2), ('b', ctypes.c_short * 5), ('dmFormName', W.WCHAR * 32), ('dmLogPixels', W.WORD),
                ('dmBitsPerPel', W.DWORD), ('dmPelsWidth', W.DWORD), ('dmPelsHeight', W.DWORD),
                ('dmDisplayFlags', W.DWORD), ('dmDisplayFrequency', W.DWORD), ('rest', W.DWORD * 8)]


dm = DEVMODEW()
dm.a[2] = ctypes.sizeof(dm)
u32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
print('display: %dx%d %d bpp %d Hz' % (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmBitsPerPel, dm.dmDisplayFrequency))

SPI = {'GETBEEP': 1, 'GETMOUSE(3)': 3, 'GETBORDER': 5, 'GETKEYBOARDSPEED': 10, 'GETSCREENSAVETIMEOUT': 14,
       'GETSCREENSAVEACTIVE': 16, 'GETKEYBOARDDELAY': 22, 'GETICONTITLEWRAP': 25, 'GETMENUDROPALIGNMENT': 27,
       'GETDRAGFULLWINDOWS': 38, 'GETMOUSETRAILS': 94, 'GETSNAPTODEFBUTTON': 95, 'GETWHEELSCROLLLINES': 104,
       'GETMENUSHOWDELAY': 106, 'GETMOUSESPEED': 112, 'GETFONTSMOOTHING': 74, 'GETKEYBOARDCUES': 0x100A,
       'GETMOUSEHOVERTIME': 102, 'GETLOWPOWERACTIVE': 83, 'GETPOWEROFFACTIVE': 84}
for name, n in SPI.items():
    v = (ctypes.c_int * 3)()
    u32.SystemParametersInfoW(n, 0, v, 0)
    print('SPI_%s: %s' % (name, list(v) if n == 3 else v[0]))
wp = ctypes.create_unicode_buffer(260)
u32.SystemParametersInfoW(0x73, 260, wp, 0)
print('SPI_GETDESKWALLPAPER: %s' % wp.value)
print('double-click time: %d; swapped buttons: %d; caret blink: %d' % (
    u32.GetDoubleClickTime(), u32.GetSystemMetrics(23), u32.GetCaretBlinkTime()))
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
        print('cursor scheme: %r' % (winreg.QueryValueEx(k, '')[0],))
except OSError:
    print('cursor scheme: (none)')
