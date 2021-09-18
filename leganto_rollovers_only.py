#!/usr/bin/env python
from leganto_rollover import rollover_report
import sys
import pickle


def main(argv):
    print(argv)
    if len(argv) < 4:
        sys.exit(1)

    apikey = (argv[1]).strip()
    cem_file = (argv[2]).strip()
    pickle_name = (argv[3]).strip()

    smtp_user = None
    smtp_password = None

    with open("/home/leganto/leganto/smtp_user.txt", "r") as file:
        smtp_user = file.read().replace("\n", "")

    with open("/home/leganto/leganto/smtp_password.txt", "r") as file:
        smtp_password = file.read().replace("\n", "")

    with open(pickle_name, "rb") as p:
        cache_dict = pickle.load(p)

    rollover_report(
        cem_file,
        apikey,
        smtp_user,
        smtp_password,
        cache_dict["this_year"],
        cache_dict["last_year"],
        pickle_name,
    )


if __name__ == "__main__":
    main(sys.argv)
