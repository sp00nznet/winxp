/* devmgr.dll, a stand-in in the guest: main.cpl (Mouse, Keyboard) imports
 * DEVMGR!#19 DeviceCreateHardwarePage(hwndParent, guid) statically, and
 * Windows 2000's devmgr pulls in setupapi, cfgmgr32, wmi and wintrust (the
 * host's hardware). No Hardware page: NULL, as when devmgr has none. Built by
 * tools/devmgr_stub.cmd at the guest base 0x21C00000, then lifted like the rest. */
void* __stdcall DeviceCreateHardwarePage(void* hwnd, const void* guid) { (void)hwnd; (void)guid; return 0; }
