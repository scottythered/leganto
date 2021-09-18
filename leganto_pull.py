#!/usr/bin/env python
import paramiko
import sys
import time
from leganto_logger import log
from leganto_shared import slacker


def pull(leganto_pass):
    try:
        host = "libfile.lib.asu.edu"
        port = 22
        transport = paramiko.Transport((host, port))
        transport.connect(username="leganto-sftp", password=leganto_pass)
        sftp = paramiko.SFTPClient.from_transport(transport)
    except Exception as e:
        msg = (
            f"Tried to pull UTO's CEM data from Libfile but SFTP connection failed: {e}"
        )
        log.error(msg)
        slacker("Pull", msg)
    else:
        sftp.chdir("/leganto")
        today = time.strftime("%Y%m%d")

        for f in sftp.listdir():
            if f.startswith(f"leganto_export_{today}"):
                cem_file = f"cem_{today}.csv"
                log.info(f"Pulling down file {f} as '{cem_file}'")
                sftp.get(f, cem_file)

        return cem_file
