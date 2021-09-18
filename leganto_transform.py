#!/usr/bin/env python
"""
This script transforms Hyperion (CEM) query data
into Alma course loader CSV and places the
CSV into the Alma SFTP endpoint
"""
# -*- coding: utf-8 -*-
import sys
import time
import os.path
import csv
import requests
from leganto_shared import (
    fileCheck,
    processDwTnCampus,
    getStringTerm,
    handle_delete_or_suspend,
    merge_inst_and_search_ids,
    data_from_api,
    check_for_reading_lists,
    process_courses,
    get_xml_from_api,
)
from leganto_logger import log
import pandas as pd


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
        # if campus == "ASUONLI" or campus == "ICOURSE":
        # proc_dept = "FLETCHER"
    elif college_code in noble_college_codes:
        proc_dept = "NOBLE"
    elif college_code == "HI":
        proc_dept = "DESIGN"
    elif college_code == "LW":
        proc_dept = "LAW"
    elif college_code is None:
        log.error("College code [None] for Tempe does not have a match")
        proc_dept = "COURSE_UNIT"
    else:
        # raise ValueError(f"College code {college_code} for Tempe does not have a match")
        log.error(f"College code {college_code} for Tempe does not have a match")
        proc_dept = "COURSE_UNIT"
    return {"proc_dept": proc_dept}


def check_for_single_course(sln, year, apikey):
    search_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=section~{sln}%20AND%20year~{year}&apikey={apikey}"
    # print(search_url)
    tree2 = data_from_api(search_url)
    record_count = int(tree2["total_record_count"])
    if record_count == 1:
        # print("the copy course exists with section match")
        rec_id = tree2["course"][0]["id"]
        old_course_code = tree2["course"][0]["code"]
        if check_for_reading_lists(rec_id, apikey) is True:
            # do rollover
            return old_course_code
    elif record_count > 1:
        return False
        # print("there were multiple courses returned")
        # print("cannot reliably proceed")
    else:
        # print("no course match")
        search_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=searchable_ids~{sln}%20AND%20year~{year}&apikey={apikey}"
        # print(search_url)
        tree3 = data_from_api(search_url)
        record_count = int(tree3["total_record_count"])
        if record_count == 1:
            # print("the copy course exists with search_id match")
            rec_id = tree3["course"][0]["id"]
            old_course_code = tree3["course"][0]["code"]
            if check_for_reading_lists(rec_id, apikey) is True:
                # do rollover
                return old_course_code
        elif record_count > 1:
            return False
            # print("there were multiple courses returned")
            # print("cannot reliably proceed")
        else:
            # print("no course match")
            return False


def transform(inFile, apikey, perform_rollovers, this_year_cache, last_year_cache):

    if perform_rollovers == "True" or perform_rollovers is True:
        perform_rollovers = True
    else:
        perform_rollovers = False

    # filecheck inputs
    fileCheck(inFile)

    # output file
    outFile = time.strftime("%Y%m%d%H%M%S") + ".txt"

    # establish this year and last year
    this_year = time.strftime("%Y")
    last_year = int(this_year) - 1

    df = pd.read_csv(inFile, encoding="iso-8859-1", dtype=str, error_bad_lines=False)
    df_none = df.where(pd.notnull(df), None)
    reader = df_none.to_dict("records")
    all_rows = {}

    # loop through each row and build dict where {course_code:[row_of_alma_formatted_data]}
    for row in reader:
        course_code = row["MYASU_COURSE_IDSTRING"]
        course_status = row["COURSE_STATUS"]
        status = ""
        if course_status == "REQUESTED":
            # ignore these as they should have a different status the next day
            continue
        course_title = row["COURSE_NAME"]
        section_id = row["SLN"].replace("-", "")
        inst_asurite = row["ASURITEID"]
        if course_status == "DENIED" or course_status == "SUSPENDED":
            # print("course is not approved %s" % course_code)
            # if the course needs to be deleted
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
        elif campus == "ASUONLI" or campus == "ICOURSE":
            proc_dept = "ASU_ONLINE"
        elif campus == "TEMPE":
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
        mus_codes = ["MDC", "MHL", "MSC", "MSI", "MTC", "MUE", "MUP", "MUS"]
        law_codes = ["SDO"]
        if row["COURSE_ID"] is None:
            row["COURSE_ID"] = "-"
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
            log.error(f"No term was provided for term {term}")
            continue
        year = row["YEAR"]
        start_sync_date = row["START_SYNC_DATE"]
        end_sync_date = row["END_SYNC_DATE"]
        # reformat start_sync and end_sync to dd-mm-yyyy
        # CEM data comes in as 2018-08-13 00:00:00.000000000
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
            # print("this course_code is already present %s" % course_code)
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
        # else:
        # no course has the same course code or section id
        # print("this course stands alone with a single instructor %s" % alma_row['course_code'])
        if alma_row is not None:
            # print('course id is %s' % alma_row['course_code'])
            # check all_rows that are set to delete
            # if the course exists, then check if there are reading lists
            # if there are reading lists dont let the delete go through
            # if there are no lists then delete the course
            # if the course does not exist, dont send the delete

            if alma_row["operation"] == "DELETE":
                # print("check to see if we should send through this delete")
                # this might not be the BEST query because it will match on partial course codes
                # for example if you query with 2018Fall-X-SDO598-92898 it will find
                # a match for 2018Fall-X-SDO598-92898-3964
                course_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=code~{alma_row['course_code']}&apikey={apikey}"
                tree = get_xml_from_api(course_url)
                record_count = tree.get("total_record_count")
                if record_count is not None:
                    if int(record_count) > 0:
                        if tree.findtext(".//course/code") == alma_row["course_code"]:
                            # check for reading lists
                            course_id = tree.findtext(".//course/id")
                            rl_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?apikey={apikey}"
                            tree2 = get_xml_from_api(rl_url)
                            if tree2.find(".//reading_list") is not None:
                                log.error(
                                    f"there are reading lists for course_id {course_id}"
                                )
                                alma_row = None
                            # else:
                            # no lists, course is safe to delete
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
                    matches = filter(
                        lambda course: course["section"] == alma_row["copy_course_sln"]
                        or alma_row["copy_course_sln"] in course["search_ids"],
                        this_year_cache,
                    )
                    if len(matches) == 1:
                        log.debug(
                            f"section match in this years course {alma_row['course_code']}"
                        )
                        if check_for_reading_lists(matches[0]["id"], apikey) is True:
                            #         # do rollover
                            # print('course id is %s' % alma_row['course_code'])
                            old_course_code = matches[0]["code"]
                            log.info(f"ROLLING OVER {old_course_code}")
                            alma_row["operation"] = "ROLLOVER"
                            alma_row["old_course_code"] = old_course_code
                            alma_row["old_coursesect_id"] = alma_row["copy_course_sln"]
                elif alma_row["copy_course_year"] == last_year:
                    # print("check lasts year cache")
                    ly_matches = filter(
                        lambda course: course["section"] == alma_row["copy_course_sln"]
                        or alma_row["copy_course_sln"] in course["search_ids"],
                        last_year_cache,
                    )
                    if len(ly_matches) == 1:
                        log.debug(
                            f"section match in this years courses {alma_row['course_code']}"
                        )
                        if check_for_reading_lists(ly_matches[0]["id"], apikey) is True:
                            #         # do rollover
                            # print('course id is %s' % alma_row['course_code'])
                            old_course_code = ly_matches[0]["code"]
                            log.info(f"ROLLING OVER {old_course_code}")
                            alma_row["operation"] = "ROLLOVER"
                            alma_row["old_course_code"] = old_course_code
                            alma_row["old_coursesect_id"] = alma_row["copy_course_sln"]
                else:
                    # do the slow way if its not from the past two years
                    log.debug(f"checking for rollovers {alma_row['copy_course_year']}")
                    old_course_code = check_for_single_course(
                        alma_row["copy_course_sln"],
                        alma_row["copy_course_year"],
                        apikey,
                    )
                    if old_course_code is not False:
                        alma_row["operation"] = "ROLLOVER"
                        alma_row["old_course_code"] = old_course_code
                        alma_row["old_coursesect_id"] = alma_row["copy_course_sln"]

        if alma_row is not None:
            all_rows[alma_row["course_code"]] = alma_row

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
    return outFile
