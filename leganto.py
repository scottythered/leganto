#!/usr/bin/env python
from leganto_transform import transform
from leganto_pull import pull
from leganto_push import pusher
from leganto_logger import log
from course_caching import cacher
from leganto_rollover import rollover_report
import sys
import time

# associated with crontab entry like 47 7 * * * /Users/ezoller/Sites/leganto/leganto_run.sh


def usage():
    """Print a usage statement for this script."""
    print("Runs the Leganto pull, transform, push, and rollover processes")
    print("in succession.")
    print("Usage:")
    print("    leganto_pull_transform_pull.py <apikey>")
    print("Where:")
    print("    apikey              Alma API Key with course access")


def main(argv):
    print(argv)
    if len(argv) < 2:
        usage()
        sys.exit(1)

    apikey = (argv[1]).strip()

    leganto_pass = None
    with open("/home/leganto/leganto/leganto_pass.txt", "r") as file:
        leganto_pass = file.read().replace("\n", "")

    smtp_user = None
    smtp_password = None
    with open("/home/leganto/leganto/smtp_user.txt", "r") as file:
        smtp_user = file.read().replace("\n", "")
    with open("/home/leganto/leganto/smtp_password.txt", "r") as file:
        smtp_password = file.read().replace("\n", "")

    sftp_password = None
    with open("/home/leganto/leganto/sftp_password.txt", "r") as file:
        sftp_password = file.read().replace("\n", "")

    perform_rollovers = False

    this_years_cache, last_years_cache, pickle_name = cacher(apikey)

    cem_file = pull(leganto_pass)
    out_file = transform(
        cem_file, apikey, perform_rollovers, this_years_cache, last_years_cache
    )
    log.info(f"Transformed file: {out_file}")

    pusher(out_file, sftp_password)

    time.sleep(7200)

    rollover_report(
        cem_file,
        apikey,
        smtp_user,
        smtp_password,
        this_years_cache,
        last_years_cache,
        pickle_name,
    )


if __name__ == "__main__":
    main(sys.argv)
