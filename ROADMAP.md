# Roadmap

Explorer runs on XP's own lifted set, in Luna on Bliss
([docs/survey.md](docs/survey.md), Handoff); what is left are its gaps.

## Next
- **The resize strip**: after a resize (winmine's Intermediate, Custom) a
  strip of the old frame is left unpainted.
- **calc's width in Luna**: its window comes out 10 px narrower than its
  buttons, clipping the right column.
- **The Run dialog**: its frame is still classic and its icon blank.
- **Popup menus** (the Start menu's submenus, an app's menus) are drawn by
  the host, not themed.
- **The Start menu**: no user picture, no most-used programs list, and its
  program list.

## Later
- **Host identity**: NtEnumerateValueKey of host keys is not scrubbed, and
  secur32's GetUserNameEx formats other than SamCompatible and Display fail
  when proxied.
- **seh32's resume to 0** after a non-RPC_S code. Explorer no longer meets
  it (NetGetJoinInformation is refused before the RPC: 15 clean runs of 15),
  but the cause is not fixed.

## Out of scope
- Shipping Windows XP's files, or anything generated from them (lifted C,
  disassembly, catalogs, symbol maps): you build from your own CD. The
  address-only seeds in `work/seeds` are the one exception, kept so a relift
  reproduces.
