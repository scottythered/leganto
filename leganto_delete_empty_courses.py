#!/usr/bin/env python
"""
This script deletes courses in the given term
and year that do NOT have reading lists.
"""
from lxml import etree
import sys
import requests
import urllib

# python leganto_delete_empty_courses.py 2019 "Spring A" key


def usage():
    print("Delete courses which do not have a reading list")
    print("You will need to specify the year and the term you are looking to delete ")
    print("Usage:")
    print("  leganto_delete_empty_courses.py <year> <term> <apikey> ")
    print("Where:")
    print("  year             A year value like 2019")
    print("  term             A term value like Spring B or Summer Dynamic")
    print("  apikey           Alma API Key with course access")
    print("Output:")
    print("  No output file")


def queryByCode(code, section, apikey):
    url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?q=code~{code}%20AND%20section~{section}&apikey={apikey}"
    response = requests.get(url)
    xml_text = response.text.replace(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
    )
    tree = etree.XML(xml_text)
    return tree


def checkForReadingLists(id, apikey):
    reading_list_url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{id}?view=full&apikey={apikey}"
    response = requests.get(reading_list_url)
    xml_text = response.text.replace(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
    )
    tree = etree.XML(xml_text)
    reading_lists = tree.find(".//reading_lists/reading_list")
    if reading_lists is not None:
        return True
    else:
        return False


def deleteCourse(cid, apikey):
    url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{cid}?apikey={apikey}"
    r = requests.delete(url)
    print(f"deleted {cid}")


def get_term_courses(year, term, apikey, courses, resumption_token=None):
    report_string = "/shared/Arizona State University/Reports/Fulfillment/Courses in a Specific Term and Year"
    report_path = urllib.quote(report_string, safe="")
    filter_string = (
        """<sawx:expr xsi:type="sawx:logical" op="and"  xmlns:saw="com.siebel.analytics.web/report/v1.1"
xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <sawx:expr xsi:type="sawx:comparison" op="equal">
        <sawx:expr xsi:type="sawx:sqlExpression">"Course"."Course Term"</sawx:expr>
        <sawx:expr xsi:type="xsd:string">"""
        + term
        + """</sawx:expr>
    </sawx:expr>
    <sawx:expr xsi:type="sawx:comparison" op="equal">
        <sawx:expr xsi:type="sawx:sqlExpression">"Course"."Course Year"</sawx:expr>
        <sawx:expr xsi:type="xsd:string">"""
        + year
        + """</sawx:expr>
    </sawx:expr>
</sawx:expr>"""
    )
    filter_string = urllib.quote(filter_string, safe="")
    url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports?path={report_path}&filter={filter_string}&limit=25"
    if resumption_token:
        url = url + "&token=" + resumption_token
    url = url + "&apikey=" + apikey
    # print(url)
    response = requests.get(url)
    xml_text = response.text.replace(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
    ).replace(' xmlns="urn:schemas-microsoft-com:xml-analysis:rowset"', "")
    tree = etree.XML(xml_text)
    print(etree.tostring(tree, pretty_print=True))
    return tree


def get_all_courses(year, term, apikey):
    courses = []
    xmlresp = get_term_courses(year, term, apikey, courses)
    # print(xmlresp.findtext('.//QueryResult/IsFinished'))
    for x in xmlresp.findall(".//QueryResult/ResultXml/rowset/Row"):
        # print(etree.tostring(x, pretty_print=True))
        courses.append(x)
    for i in range(100):
        token = xmlresp.findtext(".//QueryResult/ResumptionToken")
        resp = get_term_courses(year, term, apikey, courses, token)
        if resp.findtext(".//QueryResult/IsFinished") == "false":
            for x in resp.findall(".//QueryResult/ResultXml/rowset/Row"):
                courses.append(x)
        else:
            break
    print(len(courses))
    return courses


def main(argv):
    if len(argv) < 4:
        usage(sys.stderr)
        sys.exit(1)

    # inputs
    year = argv[1]
    term = argv[2]
    apikey = argv[3]
    print(year)
    print(term)
    # print(apikey)
    courses = get_all_courses(year, term, apikey)
    last_code = None
    for c in courses:
        c_code = c.findtext(".//Column1")
        c_sec = c.findtext(".//Column2")
        if last_code == c_code:
            continue

        # query for course in api
        tree = queryByCode(c_code, c_sec, apikey)
        # print(etree.tostring(tree, pretty_print=True))
        if tree.get("total_record_count"):
            # record_count = int(tree.get('total_record_count'))
            courses = tree.findall("course")
            for c in courses:
                cid = c.findtext("id")
                rl = checkForReadingLists(cid, apikey)
                if rl:
                    # do nothing, has a reading list
                    print(f"{cid} has a reading list")
                else:
                    # delete the course, no reading list
                    print(f"{cid} should be deleted")
                    deleteCourse(cid, apikey)
        else:
            print(f"tree error for {c_code}")

        last_code = c_code


if __name__ == "__main__":
    main(sys.argv)
