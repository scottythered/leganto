import aiohttp
import asyncio
from asyncio_throttle import Throttler
import time
import math
import pickle
import sys
from leganto_logger import log
from leganto_shared import data_from_api
from datetime import datetime


def offset_rounder(x):
    rounded_offset_limit = int(math.floor(x / 100.0))
    return list(range(100, (rounded_offset_limit + 1) * 100, 100))


async def cache_worker(apiKey, client, throttler, offset_amount, year):
    headers = {"Accept-Charset": "UTF-8", "Accept": "application/json"}
    async with throttler:
        try:
            resp = None
            async with client.get(
                f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/?q=year~{year}&limit=100&offset={offset_amount}&apikey={apiKey}",
                headers=headers,
            ) as session:
                if session.status != 200:
                    resp = await session.text()
                    session.raise_for_status()
                resp = await session.json()
                return resp["course"]
        except Exception as e:
            return {"error": e, "message": resp}


async def cache_manager(apiKey, input_year, range_list):
    throttler = Throttler(rate_limit=25)
    async with aiohttp.ClientSession() as client:
        awaitables = [
            cache_worker(apiKey, client, throttler, offset, input_year)
            for offset in range_list
        ]
        results = await asyncio.gather(*awaitables)
    return results


def cache_the_courses(year, apiKey):
    url = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/?q=year~{year}&limit=100&apikey={apiKey}"
    headers = {"Accept-Charset": "UTF-8", "Accept": "application/json"}
    api_call_one = data_from_api(url)
    record_count = int(api_call_one["total_record_count"])
    offset_range_list = offset_rounder(record_count)
    year_cache_list_of_lists = asyncio.run(
        cache_manager(apiKey, year, offset_range_list)
    )
    flattened_cache_list = [
        item for sublist in year_cache_list_of_lists for item in sublist
    ]
    first_set_of_results = api_call_one["course"]
    all_results = first_set_of_results + flattened_cache_list
    log.info(f"total record count for {year} is {record_count}")
    return all_results


def process_courses(data_package, year):
    courses = []
    for course in data_package:
        try:
            if course["id"] != "":
                if "searchable_id" in course:
                    search_ids = [
                        search_id
                        for search_id in course["searchable_id"]
                        if search_id != "-"
                    ]
                else:
                    search_ids = []
                temp = {
                    "id": course["id"],
                    "link": course["link"],
                    "section": course["section"],
                    "code": course["code"],
                    "year": course["year"],
                    "search_ids": search_ids,
                }
                courses.append(temp)
        except:
            print(f"Error -- {course}")
    log.info(f"course count for {year} is {len(courses)}")
    return courses


def cacher(apikey):
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d")
    pickle_name = f"cached_courses_{current_time}.pickle"

    # establish this year and last year
    this_year = time.strftime("%Y")
    last_year = int(this_year) - 1

    log.info("caching this year's courses")
    this_year_courses = cache_the_courses(this_year, apikey)
    log.info("caching last year's courses")
    last_year_courses = cache_the_courses(last_year, apikey)

    temp_dict = {"this_year": this_year_courses, "last_year": last_year_courses}

    this_year_cache = process_courses(this_year_courses, this_year)
    last_year_cache = process_courses(last_year_courses, last_year)

    cache_dict = {"this_year": this_year_cache, "last_year": last_year_cache}
    with open(pickle_name, "wb") as p:
        pickle.dump(cache_dict, p)

    return this_year_cache, last_year_cache, pickle_name
