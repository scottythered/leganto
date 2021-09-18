#!/usr/bin/env python
"""
This script servers as a library of shared processes used by Leganto.
"""
import json
import requests
import os
import sys
from lxml import etree
from leganto_logger import log
import smtplib
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from os.path import basename


def slacker(desc, msg):
    """Handles messaging to the dedicated Leganto Slack channel."""

    slack_channel = "https://hooks.slack.com/services/XXX/XXXX/XXXXX"
    msg_header = "*Leganto " + desc + "*"
    formatted = [
        {"type": "context", "elements": [{"type": "mrkdwn", "text": msg_header}],},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": msg}},
    ]
    slackdata = {
        "text": "Leganto Status Update",
        "blocks": json.dumps(formatted),
    }
    headers = {"Content-Type": "application/json"}
    requests.post(slack_channel, json=slackdata, headers=headers)


def fileCheck(filename):
    """Determines if file 'filename' exists."""

    if not os.path.isfile(filename):
        log.error(f"File: {filename} not found. Exiting...")
        sys.exit(1)


def data_from_api(url):
    """A more thorough version of getting data from the Ex Libris API;
    created in 2020 after sdeveral instances of a noticeable decline in
    the reliability of their API services."""

    headers = {"Accept-Charset": "UTF-8", "Accept": "application/json"}
    get = False
    attempt = 0
    while get is False:
        if attempt < 6:
            try:
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    get = True
                else:
                    attempt += 1
                    time.sleep(2.5)
            except:
                attempt += 1
                time.sleep(2.5)
        else:
            get = True
    return resp.json()


def send_mail(recipient, msg_text, filename, subject_text, smtp_user, smtp_password):
    if type(filename) == str:
        files = [filename]
    elif type(filename) == list:
        files = filename

    # sender address must be verified in AWS.
    sender = "hourly@asu.edu"
    sender_name = "Leganto"
    host = "email-smtp.us-west-2.amazonaws.com"
    port = 587

    msg = MIMEMultipart()
    msg["Subject"] = subject_text
    msg["From"] = email.utils.formataddr((sender_name, sender))
    msg["To"] = recipient
    text = MIMEText(msg_text, "plain")
    msg.attach(text)

    for f in files:
        with open(f, "r") as fil:
            part = MIMEApplication(fil.read(), Name=basename(f))
        part["Content-Disposition"] = f'attachment; filename="{basename(f)}"'
        msg.attach(part)

    server = smtplib.SMTP(host, port)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(smtp_user, smtp_password)
    server.sendmail(sender, recipient, msg.as_string())
    server.close()


def process_courses(data_package, year):
    courses = []
    for course in data_package:
        if course["id"] != "":
            if "searchable_id" in course:
                search_ids = course["searchable_id"]
            else:
                search_ids = None
            temp = {
                "id": course["id"],
                "link": course["link"],
                "section": course["section"],
                "code": course["code"],
                "year": course["year"],
                "search_ids": search_ids,
            }
            courses.append(temp)
    log.info(f"course count for {year} is {len(courses)}")
    return courses


def processTempeCampus(campus, college_code):
    hayden_college_codes = [
        "AS",
        "BA",
        "CS",
        "FI",
        "GC",
        "HO",
        "LA",
        "LS",
        "PP",
        "PR",
        "SU",
        "TB",
        "TE",
        "UC",
        "GF",
    ]
    noble_college_codes = ["ES", "NH", "NU"]
    if college_code in hayden_college_codes:
        proc_dept = "HAYDEN"
        if campus == "ASUONLI" or campus == "ICOURSE":
            proc_dept = "FLETCHER"
    elif college_code in noble_college_codes:
        proc_dept = "NOBLE"
    elif college_code == "HI":
        proc_dept = "DESIGN"
    elif college_code == "LW":
        proc_dept = "LAW"
    elif college_code is None:
        log.error(f"College code [None] for Tempe does not have a match!")
        proc_dept = "COURSE_UNIT"
    else:
        log.error(f"College code {college_code} for Tempe does not have a match!")
        proc_dept = "COURSE_UNIT"

    return {"proc_dept": proc_dept}


def processDwTnCampus(campus, college_code):
    if college_code == "LW":
        proc_dept = "LAW"
    else:
        proc_dept = "DOWNTOWN"
    return {"proc_dept": proc_dept}


def getStringTerm(course_code, term):
    term_string = ""
    split_code = course_code.split("-")
    if term == "1":
        if split_code[0].endswith("g") or split_code[0].endswith("gC"):
            term_string = "SPRING"
        elif split_code[0].endswith("gA"):
            term_string = "TERM4"
        elif split_code[0].endswith("gB"):
            term_string = "TERM5"
        elif split_code[0].endswith("gDYN"):
            term_string = "TERM6"
        else:
            log.error(
                f"It's a spring course but we can't determine the term {term} for {course_code}"
            )
    elif term == "4":
        # summer
        if split_code[0].endswith("r") or split_code[0].endswith("rC"):
            term_string = "SUMMER"
        elif split_code[0].endswith("rA"):
            term_string = "TERM7"
        elif split_code[0].endswith("rB"):
            term_string = "TERM8"
        elif split_code[0].endswith("rDYN"):
            term_string = "SEMESTER1"
        else:
            log.error(
                f"It's a summer course but we can't determine the term {term} for {course_code}"
            )
    elif term == "7":
        # fall
        if split_code[0].endswith("l") or split_code[0].endswith("lC"):
            term_string = "AUTUMN"
        elif split_code[0].endswith("lA"):
            term_string = "TERM1"
        elif split_code[0].endswith("lB"):
            term_string = "TERM2"
        elif split_code[0].endswith("lDYN"):
            term_string = "TERM3"
        else:
            log.error(
                f"It's a fall course but we can't determine the term {term} for {course_code}"
            )
    return term_string


def handle_delete_or_suspend(current_row, other_row, all_rows):
    if current_row["operation"] == "DELETE":
        return None
    if other_row["operation"] == "DELETE":
        all_rows[other_row["course_code"]] = current_row
        return current_row


def merge_inst_and_search_ids(current_row, other_row, all_rows):
    insts = []
    if other_row["inst_1"] != "":
        insts.append(other_row["inst_1"])
    if other_row["all_inst"] != "":
        ts = other_row["all_inst"].split(",")
        for t in ts:
            if t not in insts:
                insts.append(t)
    if current_row["inst_1"] != "" and current_row["inst_1"] not in insts:
        insts.append(current_row["inst_1"])
    other_row["all_inst"] = ",".join(insts)
    other_row["inst_1"] = ""
    search_ids = []
    if other_row["search_id_1"] != "":
        search_ids.append(other_row["search_id_1"])
    if other_row["all_search_ids"] != "":
        ss = other_row["all_search_ids"].split(",")
        for s in ss:
            if s not in search_ids:
                search_ids.append(s)
    if (
        current_row["search_id_1"] != ""
        and current_row["search_id_1"] not in search_ids
    ):
        search_ids.append(current_row["search_id_1"])
    if current_row["section_id"] != "" and current_row["section_id"] not in search_ids:
        search_ids.append(current_row["section_id"])
    if len(search_ids) > 10:
        search_ids = search_ids[:10]
    if int(other_row["section_id"]) > int(current_row["section_id"]):
        if current_row["section_id"] not in search_ids:
            search_ids.append(current_row["section_id"])
        if other_row["section_id"] not in search_ids:
            search_ids.append(other_row["section_id"])
        other_row["section_id"] = current_row["section_id"]
    other_row["all_search_ids"] = ",".join(search_ids)
    other_row["search_id_1"] = ""
    current_row = None
    return current_row, other_row


def get_xml_from_api(url):
    r = requests.get(url)
    xml_text = r.text.replace(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
    )
    tree = etree.XML(xml_text)
    return tree


def check_for_reading_lists(id, apikey):
    reading_list_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{id}?view=full&apikey={apikey}"
    tree = get_xml_from_api(reading_list_url)
    reading_lists = tree.find(".//reading_lists/reading_list")
    if reading_lists is not None:
        return True
    else:
        return False


def check_for_single_course(sln, year, apikey):
    search_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=section~{sln}%20AND%20year~{year}&apikey={apikey}"
    tree2 = get_xml_from_api(search_url)
    record_count = int(tree2.get("total_record_count"))
    if record_count == 1:
        rec_id = tree2.findtext(".//course/id")
        old_course_code = tree2.findtext(".//course/code")
        if check_for_reading_lists(rec_id, apikey) is True:
            # do rollover
            return old_course_code
        else:
            return False
    elif record_count > 1:
        return False
    else:
        search_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=searchable_ids~{sln}%20AND%20year~{year}&apikey={apikey}"
        tree = get_xml_from_api(search_url)
        record_count = int(tree.get("total_record_count"))
        if record_count == 1:
            rec_id = tree.findtext(".//course/id")
            old_course_code = tree2.findtext(".//course/code")
            if check_for_reading_lists(rec_id, apikey) is True:
                # do rollover
                return old_course_code
            else:
                return False
        elif record_count > 1:
            return False
        else:
            return False
