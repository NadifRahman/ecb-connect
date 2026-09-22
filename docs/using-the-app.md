# Using ECBE Connect

## Connect

1. Open **ECBE Connect - Unofficial** and acknowledge the first-run notice.
2. Enter your ECBE username. The default gateway is `pascal.ecb.torontomu.ca`.
3. Leave the preferred local port at 5900 unless another program uses it.
4. Optionally select the installed RealVNC executable if automatic detection fails.
5. Optionally enable **Remember ECBE password**. This uses the operating-system keychain and never
   a normal file.
6. Select **Connect and open VNC**.
7. Verify the SSH fingerprint on first use. If you cannot verify it, cancel and contact ECBE.
8. Enter a fresh six-digit code for each `Verification code:` prompt.

When ready, RealVNC opens at `127.0.0.1::5900` or the next local port selected by the app.
RealVNC launches with its address-book integration enabled, allowing its own optional
**Remember password** setting to apply to later connections at the same local address. ECBE
Connect never receives or passes that password. A different fallback port is a different RealVNC
address and may require saving the password once for that address.

## Keep the connection running

Closing the main window while connected hides it in the notification area, menu bar, or system
tray. The tray icon remains visible and the tunnel stays active. Use its menu to reopen the window,
copy the VNC address, reconnect, disconnect, or quit.

On a Linux desktop without a supported tray, ECBE Connect remains minimized in the taskbar instead.

## CLI

```text
ecbe-connect config --username YOUR_ID
ecbe-connect doctor
ecbe-connect connect
```

The CLI holds the tunnel in the foreground. Press `Ctrl+C` to disconnect.

Other commands:

```text
ecbe-connect sessions
ecbe-connect passwd
ecbe-connect kill WORKSTATION
ecbe-connect clear-data
ecbe-connect disclaimer
```

`kill` can destroy a remote session and lose unsaved work, so it requires confirmation.

## Disconnect safely

Use **Disconnect** before changing networks, shutting down, or removing ECBE Connect. Quitting the
GUI also disconnects after confirmation. Closing only the RealVNC window does not automatically
close the SSH tunnel.
