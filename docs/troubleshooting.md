# Troubleshooting

Start with `ecbe-connect doctor`. It checks the configured gateway, DNS, SSH port, preferred local
port, installed viewer, and secure keychain without attempting a login.

## Authentication keeps failing

- Confirm that the first prompt uses the ECBE password, not the VNC or RealVNC-account password.
- Enter a newly displayed six-digit `ECB_Dept_AuthCode`; codes expire every 30 seconds.
- A second password/MFA round may be the department starting the assigned workstation.
- ECBE Connect stops after bounded attempts. It does not retry indefinitely.

## RealVNC says the password is wrong

Use the separate VNC password created by `vncconnect`, not the ECBE password. Change it with:

```text
ecbe-connect passwd
```

After repeated incorrect attempts, wait before retrying so the server-side security delay can
expire.

## RealVNC cannot connect

- Use the address displayed by ECBE Connect, including the double colon, such as
  `127.0.0.1::5900`.
- Keep ECBE Connect running in the tray.
- If port 5900 was busy, the app may display 5901 or another local port.
- Configure the RealVNC executable manually if viewer detection failed.

## SSH host key changed

Do not click through a changed-key warning. A legitimate server replacement and an interception
attempt can look identical. Contact [ECBE technical support](https://www.ecb.torontomu.ca/contact.html)
and verify the new fingerprint before removing the saved key.

## The session opens but the Linux desktop is locked

Unlock the remote Linux screen with the ECBE account password. Do not log out from the Linux
desktop unless you intend to end the session; the older departmental guide warns that logging out
can make the VNC session unusable until it is killed and recreated.

## The app disappeared

While connected, closing the window hides it in the notification area/menu bar/system tray. Open
the tray icon and choose **Show ECBE Connect**. On Linux without tray support, look for a minimized
taskbar window.

## Safe problem reports

Never attach passwords, MFA codes, full terminal transcripts, screenshots containing student IDs,
or private host keys. Use the app's sanitized event log and describe only the failed stage.

