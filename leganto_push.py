#!/usr/bin/env python
import paramiko
import sys
from leganto_shared import slacker
from leganto_logger import log


def pusher(file_to_send, sftp_pass):
    try:
        host = "libfile.lib.asu.edu"
        port = 22
        transport = paramiko.Transport((host, port))
        transport.connect(username="lsp-sftp", password=sftp_pass)
        sftp = paramiko.SFTPClient.from_transport(transport)
    except Exception as e:
        msg = f"Tried to push Leganto data to Libfile but SFTP connection failed: {e}"
        log.error(msg)
        slacker("Push", msg)
    else:
        sftp.chdir("/share/LSP-SFTP/prod/course_loader")
        if file_to_send not in sftp.listdir():
            sftp.put(file_to_send, file_to_send)
        if file_to_send in sftp.listdir():
            msg = f"successfully transferred {file_to_send}"
            log.info(msg)
            slacker("Push", msg)
        else:
            slacker("Push", "Leganto_push failed, advise checking it out.")
