# First-time ECBE setup

Complete these steps before expecting ECBE Connect to work. Account creation, password resets,
and authenticator enrollment remain official ECBE processes and are not performed by this app.

## 1. Confirm your ECBE account

You need an active account on the ECBE departmental network. Your login is normally your TMU
short ID. Account or login problems should be sent to
[ECBE technical support](https://www.ecb.torontomu.ca/contact.html).

## 2. Enroll `ECB_Dept_AuthCode`

ECBE currently requires two-factor authentication for SSH. The department's network guide says
students enroll the `ECB_Dept_AuthCode` token from an ECBE lab workstation and scan its QR code
with Google Authenticator.

The resulting six-digit code changes every 30 seconds. ECBE Connect asks for a fresh code whenever
the server presents `Verification code:`. It does not copy or store the enrollment seed.

Follow the current [ECBE Network User's Guide](https://www.ecb.torontomu.ca/guides/user/) for the
authoritative enrollment procedure. If its instructions differ from this guide, follow ECBE's
version.

## 3. Install a VNC viewer

Install RealVNC Viewer from the
[official RealVNC download page](https://www.realvnc.com/en/connect/download/viewer/). ECBE Connect
does not redistribute or silently install it.

The modern viewer uses an explicit port address:

```text
127.0.0.1::5900
```

The double colon means "use TCP port 5900." The older `127.0.0.1:0` display notation shown in the
2020 guide may not work in the current RealVNC interface.

## 4. Understand the three secrets

| Secret | Used for | Storage in ECBE Connect |
|---|---|---|
| ECBE password | SSH and Linux screen unlock | Prompted, or optional OS keychain |
| Six-digit verification code | Each SSH MFA challenge | Never stored |
| VNC password | VNC server authentication | Never stored by ECBE Connect |

Do not reuse your ECBE password as your VNC password.

## 5. First VNC session

On the first connection, the department's `vncconnect` tool may ask you to create and verify a
separate VNC password. ECBE Connect relays those masked prompts. RealVNC asks for that password
when the viewer opens and may offer to remember it in RealVNC's own password store.

The department may terminate sessions on a schedule. Treat the remote desktop as temporary and
save coursework regularly.

