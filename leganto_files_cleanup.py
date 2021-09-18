#!/usr/bin/env python
"""
This script removes pickle, log, CSV, and text files on the LSP-Sync server
that are older than 45 days.
"""
import os
import re
from datetime import datetime
from tqdm import tqdm


def main():
    now = datetime.now()
    ls = list(filter(os.path.isfile, os.listdir()))
    filtered = []
    tracker = 0

    for file in ls:
        if file.endswith(".csv.pickle"):
            filtered.append(file)
        elif file.endswith(".log"):
            filtered.append(file)
        elif file.endswith(".csv"):
            filtered.append(file)
        elif file.endswith(".txt"):
            if re.match("^\d{14}\.txt$", file):
                filtered.append(file)
        else:
            pass

    for file in tqdm(filtered):
        update_date = datetime.fromtimestamp(os.path.getmtime(file))
        diff = now - update_date
        if diff.days > 45:
            os.remove(file)
            tracker += 1
        else:
            pass

    if tracker > 0:
        print(f"Removed {tracker} Leganto files for you.")
    else:
        print("All Leganto files too new to delete.")


if __name__ == "__main__":
    main()
