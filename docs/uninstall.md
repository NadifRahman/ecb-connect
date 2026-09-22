# Uninstall and erase local data

## Before uninstalling

Disconnect the active tunnel from the main window or tray menu. Save all remote work first.

## Erase ECBE Connect data

In the GUI, choose **File > Clear local data**. In the CLI:

```text
ecbe-connect clear-data
```

After confirmation this removes the app configuration, rotating logs, saved SSH host keys, and the
ECBE password entry created by this app in the OS keychain. It does not modify RealVNC's password
store or any files in the ECBE account.

## Remove the application

Use the operating system's normal uninstall process or delete the portable application directory.
If the clear-data command was not run, consult the `platformdirs` location for an application named
`ECBE Connect` under the current user's configuration, cache, and log directories.

