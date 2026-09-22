# Manual connection fallback

Use these steps if ECBE Connect is unavailable or behaves differently from the official service.
They preserve the same workflow described by the department while using the current gateway name
and explicit RealVNC port syntax.

Replace `YOUR_ID`, `WORKSTATION`, and `REMOTE_PORT` with values from your own session.

## 1. Log in to Pascal

Open PowerShell, Terminal, or another OpenSSH terminal:

```text
ssh YOUR_ID@pascal.ecb.torontomu.ca
```

On first use, verify the displayed host-key fingerprint before accepting it. Enter your ECBE
password and a fresh `ECB_Dept_AuthCode` when prompted.

## 2. Start or find the VNC session

At the Pascal prompt:

```text
vncconnect
```

If this is your first session, create a separate VNC password. If a workstation must be started,
`vncconnect` may ask for the ECBE password and another fresh verification code.

The output includes a command resembling:

```text
ssh -C -L 127.0.0.1:5900:WORKSTATION:REMOTE_PORT YOUR_ID@pascal.ecb.torontomu.ca
```

The remote port is assigned by ECBE and is not necessarily 5901. A captured working example used
5902.

## 3. Open the tunnel locally

Exit the first Pascal shell. In a new local terminal, run the exact command printed by your own
session. For example:

```text
ssh -C -L 127.0.0.1:5900:cmp92.ee.ryerson.ca:5902 YOUR_ID@pascal.ecb.torontomu.ca
```

Authenticate again and leave this terminal open. Closing it closes the tunnel.

## 4. Open RealVNC

Use a direct connection to:

```text
127.0.0.1::5900
```

Enter the separate VNC password. A warning that the direct VNC connection itself is unencrypted
is expected in this architecture because its traffic travels inside the encrypted SSH tunnel and
the local listener is available only on your own computer.

## Maintenance commands

Run these only at the Pascal prompt:

```text
vncconnect list
vncconnect passwd
vncconnect kill WORKSTATION
```

Killing a session can discard unsaved work. The beta intentionally does not automate
`vncconnect reset`, workstation scanning, or targeted creation of extra sessions.
