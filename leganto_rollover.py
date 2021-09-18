#!/usr/bin/env python
from leganto_shared import (
    check_for_single_course,
    check_for_reading_lists,
    get_xml_from_api,
    merge_inst_and_search_ids,
    handle_delete_or_suspend,
    getStringTerm,
    processDwTnCampus,
    processTempeCampus,
    slacker,
    send_mail,
    fileCheck,
)
import os
import pandas as pd
import time
from leganto_logger import log
import pickle
import requests
from lxml import etree


def rollover_report(
    inFile, apikey, smtp_user, smtp_password, this_year_cache, last_year_cache, pickle
):
    perform_rollovers = True

    # filecheck inputs
    fileCheck(inFile)

    # output file
    outFile = f"rollover_{time.strftime('%Y%m%d%H%M%S')}.csv"

    this_year = time.strftime("%Y")
    last_year = int(this_year) - 1

    df = pd.read_csv(inFile, encoding="iso-8859-1", dtype=str, error_bad_lines=False)
    df_none = df.where(pd.notnull(df), None)
    reader = df_none.to_dict("records")
    all_rows = {}

    hayden_campuses = [
        "CALHC",
        "CHANDGI",
        "EAC",
        "HAINAN",
        "MESATEM",
        "OTHERAZ",
        "OTHERUS",
        "OUTSIDE",
        "SCOTTSD",
        "TUCSON",
    ]

    # loop through each row and build dict where
    # {course_code:[row_of_alma_formatted_data]}
    for row in reader:
        course_code = row["MYASU_COURSE_IDSTRING"]
        if course_code.startswith("2021Spring") or course_code.startswith("2021Summer"):
            continue
        course_status = row["COURSE_STATUS"]
        status = ""
        if course_status == "REQUESTED":
            # ignore these as they should have a different status the next day
            continue
        course_title = row["COURSE_NAME"]
        section_id = row["SLN"].replace("-", "")
        inst_asurite = row["ASURITEID"]
        if course_status == "DENIED" or course_status == "SUSPENDED":
            # the course needs to be deleted
            status = "DELETE"
        college_code = row["COLLEGE_OR_DIVISION_CODE"]
        campus = row["CAMPUS"]
        hayden_campuses = [
            "CALHC",
            "CHANDGI",
            "EAC",
            "HAINAN",
            "MESATEM",
            "OTHERAZ",
            "OTHERUS",
            "OUTSIDE",
            "SCOTTSD",
            "TUCSON",
        ]
        if campus in hayden_campuses:
            proc_dept = "HAYDEN"
        elif campus == "ASUONLI" or campus == "ICOURSE" or campus == "TEMPE":
            res = processTempeCampus(campus, college_code)
            proc_dept = res["proc_dept"]
        elif campus == "DTPHX" or campus == "PHOENIX":
            res = processDwTnCampus(campus, college_code)
            proc_dept = res["proc_dept"]
        elif campus == "GLENDALE" or campus == "WEST":
            proc_dept = "FLETCHER"
        elif campus == "POLY":
            proc_dept = "POLYTECHNIC"
        elif campus == "TBIRD":
            proc_dept = "THUNDERBIRD"
        else:
            proc_dept = "HAYDEN"
            log.error(f"Campus Code {campus} not in known values")
        acad_dept = college_code
        if row["COURSE_ID"] is None:
            row["COURSE_ID"] = "-"
        mus_codes = ["MDC", "MHL", "MSC", "MSI", "MTC", "MUE", "MUP", "MUS"]
        law_codes = ["SDO"]
        if row["COURSE_ID"][0:3] in mus_codes:
            proc_dept = "MUSIC"
        if row["COURSE_ID"][0:3] in law_codes:
            proc_dept = "LAW"
        if course_code[0:3] == "DEV":
            proc_dept = "COURSE_UNIT"
        term = row["TERM"]
        if term:
            term_string = getStringTerm(course_code, term)
        else:
            log.error(f"No term was provided {term}")
            continue
        year = row["YEAR"]
        start_sync_date = row["START_SYNC_DATE"]
        end_sync_date = row["END_SYNC_DATE"]
        sdate = start_sync_date.split(" ")[0]
        split_sdate = sdate.split("-")
        s_dd = split_sdate[2]
        s_mm = split_sdate[1]
        s_year = split_sdate[0]
        start_date = s_dd + "-" + s_mm + "-" + s_year
        edate = end_sync_date.split(" ")[0]
        split_edate = edate.split("-")
        e_dd = split_edate[2]
        e_mm = split_edate[1]
        e_year = split_edate[0]
        end_date = e_dd + "-" + e_mm + "-" + e_year
        search_id_1 = row["COURSE_ID"]
        if row["COPY_COURSE_SLN"].replace(",", ""):
            copy_course_sln = row["COPY_COURSE_SLN"].replace(",", "")
        else:
            copy_course_sln = ""
        if row["COPY_COURSE_SEMESTER_YEAR"]:
            copy_course_year = row["COPY_COURSE_SEMESTER_YEAR"]
        else:
            copy_course_year = ""
        if row["COPY_COURSE_ID"]:
            copy_course_section = row["COPY_COURSE_ID"]
        else:
            copy_course_section = ""
        if row["COPY_COURSE_SEMESTER_TERM"]:
            copy_course_term = row["COPY_COURSE_SEMESTER_TERM"]
        else:
            copy_course_term = ""

        alma_row = {
            "course_code": course_code,
            "course_title": course_title,
            "section_id": section_id,
            "acad_dept": acad_dept,
            "proc_dept": proc_dept,
            "term": term_string,
            "term2": "",
            "term3": "",
            "term4": "",
            "start_date": start_date,
            "end_date": end_date,
            "num_participants": "",
            "hours": "",
            "year": year,
            "search_id_1": search_id_1,
            "search_id_2": "",
            "all_search_ids": "",
            "inst_1": inst_asurite,
            "inst_2": "",
            "inst_3": "",
            "inst_4": "",
            "inst_5": "",
            "inst_6": "",
            "inst_7": "",
            "inst_8": "",
            "inst_9": "",
            "inst_10": "",
            "all_inst": "",
            "operation": status,
            "old_course_code": "",
            "old_course_sect_id": "",
            "copy_course_sln": copy_course_sln,
            "copy_course_year": copy_course_year,
            "copy_course_term": copy_course_term,
            "copy_course_section": copy_course_section,
        }

        if all_rows.get(alma_row["course_code"]):
            # there is a duplicate for the course_code
            other_row = all_rows.get(alma_row["course_code"])
            if status == "" and other_row["operation"] == "":
                # statuses are both approved
                # merge instructors and searchable_ids
                alma_row, updated_other_row = merge_inst_and_search_ids(
                    alma_row, other_row, all_rows
                )
                other_row = updated_other_row
            else:
                alma_row = handle_delete_or_suspend(alma_row, other_row, all_rows)
            # do not dedup based on section id and not course_code
            # this has to be allowed to be a separate course
            # it could be the dev version for example
        if alma_row is not None:
            # check all_rows that are set to delete
            # if the course exists, then check if there are reading lists
            # if there are reading lists dont let the delete go through
            # if there are no lists then delete the course
            # if the course does not exist, dont send the delete
            if alma_row["operation"] == "DELETE":
                # this might not be the BEST query because it will match on partial course codes
                # for example if you query with 2018Fall-X-SDO598-92898 it will find
                # a match for 2018Fall-X-SDO598-92898-3964
                course_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=code~{alma_row['course_code']}&apikey={apikey}"
                tree = get_xml_from_api(course_url)
                record_count = int(tree.get("total_record_count"))
                if record_count > 0:
                    if tree.findtext(".//course/code") == alma_row["course_code"]:
                        # check for reading lists
                        course_id = tree.findtext(".//course/id")
                        rl_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?apikey={apikey}"
                        tree2 = get_xml_from_api(rl_url)
                        if tree2.find(".//reading_list") is not None:
                            alma_row = None
                else:
                    # course does not exist in alma
                    # pointless to send a delete on an nonexist course
                    alma_row = None

            # now that the all_rows are deduped, lets look for any
            # possible rollovers based on the copy_course data
            log.debug(f"perform_rollovers is {perform_rollovers}")
            if (
                alma_row
                and alma_row["copy_course_sln"] != "-"
                and int(alma_row["copy_course_sln"]) != 0
            ):
                log.debug(f"copy_course_sln is {alma_row['copy_course_sln']}")
            if (
                perform_rollovers is True
                and alma_row
                and int(alma_row["copy_course_sln"]) != 0
            ):
                # check the cache for the year of the course
                # if the year isn't this year or last year
                # then go the manual route
                # otherwise look up the course in the cache
                if alma_row["copy_course_year"] == this_year:
                    # print("check this years cache")
                    matches = list(
                        filter(
                            lambda course: course["section"]
                            == alma_row["copy_course_sln"]
                            or alma_row["copy_course_sln"] in course["search_ids"],
                            this_year_cache,
                        )
                    )
                    if len(matches) == 1:
                        log.info(
                            f"section match in this years course {alma_row['course_code']}"
                        )
                        if check_for_reading_lists(matches[0]["id"], apikey) is True:
                            # do rollover
                            old_course_code = matches[0]["code"]
                            log.info(f"ROLLING OVER {old_course_code}")
                            alma_row["operation"] = "ROLLOVER"
                            alma_row["old_course_code"] = old_course_code
                            alma_row["old_course_sect_id"] = alma_row["copy_course_sln"]
                elif alma_row["copy_course_year"] == last_year:
                    ly_matches = list(
                        filter(
                            lambda course: course["section"]
                            == alma_row["copy_course_sln"]
                            or alma_row["copy_course_sln"] in course["search_ids"],
                            last_year_cache,
                        )
                    )
                    if len(ly_matches) == 1:
                        log.info(
                            f"section match in last years courses {alma_row['course_code']}"
                        )
                        if check_for_reading_lists(ly_matches[0]["id"], apikey) is True:
                            # do rollover
                            old_course_code = ly_matches[0]["code"]
                            log.info(f"ROLLING OVER {old_course_code}")
                            alma_row["operation"] = "ROLLOVER"
                            alma_row["old_course_code"] = old_course_code
                            alma_row["old_course_sect_id"] = alma_row["copy_course_sln"]
                else:
                    # do the slow way if its not from the past two years
                    old_course_code = check_for_single_course(
                        alma_row["copy_course_sln"],
                        alma_row["copy_course_year"],
                        apikey,
                    )
                    if old_course_code is not False:
                        alma_row["operation"] = "ROLLOVER"
                        alma_row["old_course_code"] = old_course_code
                        alma_row["old_course_sect_id"] = alma_row["copy_course_sln"]

        if alma_row is not None and alma_row["operation"] == "ROLLOVER":
            all_rows[alma_row["course_code"]] = alma_row

    try:
        with open(outFile, "w") as outfile:
            fields = [
                "Course Code",
                "Course Title",
                "Section ID",
                "Academic Department",
                "Processing Department",
                "Term1",
                "Term2",
                "Term3",
                "Term4",
                "Start Date",
                "End Date",
                "Number of Participants",
                "Weekly Hours",
                "Year",
                "Searchable ID 1",
                "Searchable ID 2",
                "ALL_SEARCHABLE_IDS",
                "Instructor 1",
                "Instructor 2",
                "Instructor 3",
                "Instructor 4",
                "Instructor 5",
                "Instructor 6",
                "Instructor 7",
                "Instructor 8",
                "Instructor 9",
                "Instructor 10",
                "ALL_INSTRUCTORS",
                "Operation",
                "Old Course Code",
                "Old Course Section ID",
            ]
            outfile.write("\t".join(fields) + "\n")
            for key, val in all_rows.items():
                # remove unnecessary copy course fields
                # and reorder dict to specific alma order and make list
                arr = [
                    val["course_code"],
                    val["course_title"],
                    val["section_id"],
                    val["acad_dept"],
                    val["proc_dept"],
                    val["term"],
                    val["term2"],
                    val["term3"],
                    val["term4"],
                    val["start_date"],
                    val["end_date"],
                    val["num_participants"],
                    val["hours"],
                    val["year"],
                    val["search_id_1"],
                    val["search_id_2"],
                    val["all_search_ids"],
                    val["inst_1"],
                    val["inst_2"],
                    val["inst_3"],
                    val["inst_4"],
                    val["inst_5"],
                    val["inst_6"],
                    val["inst_7"],
                    val["inst_8"],
                    val["inst_9"],
                    val["inst_10"],
                    val["all_inst"],
                    val["operation"],
                    val["old_course_code"],
                    val["old_course_sect_id"],
                ]
                arr = ["" if v is None else v for v in arr]
                outfile.write("\t".join(arr) + "\n")
    except Exception as e:
        file_write_exception = True
        file_write_err_msg = f"CSV output failed -- {e}."
    else:
        file_write_exception = False

    if file_write_exception:
        msg = f"{file_write_err_msg}"
        slacker("Rollover Daily Report", msg)
    else:
        try:
            send_mail(
                "HaydenReserve@asu.edu",
                f"Attached is the daily potential rollover report {outFile} with {len(all_rows)} rows",
                outFile,
                "Daily Potential Rollover Report",
                smtp_user,
                smtp_password,
            )
        except Exception as e:
            slacker(
                "Rollover Daily Report",
                f"Couldn't email rollover report {outFile}: {e}",
            )
        else:
            msg = f"End of script reached, rollover report {outFile} sent with {len(all_rows)} rows."
            slacker("Rollover Daily Report", msg)
            os.remove(pickle)
