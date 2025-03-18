#!/usr/bin/env python
"""Backend server for traffic record database."""

# import the various libraries needed
import http.cookies as Cookie                              # some cookie handling support
from http.server import BaseHTTPRequestHandler, HTTPServer # the heavy lifting of the web server
import urllib                                              # some url parsing support
import sqlite3                                             # sql database
import random                                              # generate random numbers
import time                                                # needed to record when stuff happened
import json                                                # support for json encoding
import sys                                                # needed for agument handling
from datetime import datetime
from collections import Counter


def handle_undo_request(iuser, imagic, content):
    """Undo an existing traffic record."""

    response  = []

    sessionid = handle_validate(iuser, imagic)
    if sessionid == 0:
        response.append(build_response_redirect('/login.html'))
        return ['', '', response]

    ## CODE NEEDED HERE
    ## Add code here to undo a matching vehicle if one exists.
    ## Otherwise, report an error that there is no match.
    ## Undoing does not delete an entry. It adds an equal but opposite entry

    # First check that all the arguments are present

    try:
        location = content['location']
    except:
        response.append(build_response_message(204,"Location field missing from request."))
        return [iuser,imagic, response]

    try:
        vtype = content['type']
    except:
        response.append(build_response_message(205,"Type field missing from request."))
        return [iuser,imagic, response]

    try:
        occupancy = content['occupancy']
    except:
        response.append(build_response_message(206,"Occupancy field missing from request."))
        return [iuser,imagic, response]

    # Then check that they match the existing records.

    try:
        sessionid = int(sessionid)
        if do_database_fetchone(f"SELECT * FROM traffic"
                                f" WHERE sessionid = {sessionid}")is None:
            raise IndexError

    except IndexError:
        response.append(build_response_message(104,"Session id does not"
                                                       " match existing record."))
        return [iuser,imagic, response]

    try:
        location = int(location)
        if do_database_fetchone(f"SELECT * FROM traffic WHERE "
            f"locationid = {location} AND sessionid = {sessionid}")is None:
            raise IndexError

    except IndexError:
        response.append(build_response_message(105,"Location field"
                                                       " does not match existing record."))
        return [iuser,imagic, response]

    try:
        vtype = int(vtype)
        vtype_query = (f"SELECT * FROM traffic WHERE locationid = {location}"
                        f" AND type = {vtype} AND sessionid = {sessionid}")
        if do_database_fetchone(vtype_query)is None:
            raise IndexError

    except IndexError:
        response.append(build_response_message(106,"Vehicle type field "
                                                       "does not match existing record."))
        return [iuser,imagic, response]

    try:
        occupancy = int(occupancy)

        occ_query = (f"SELECT * FROM traffic WHERE locationid = {location} AND type = "
                         f"{vtype} AND occupancy = {occupancy} AND sessionid = {sessionid}")
        if do_database_fetchone(occ_query)is None:
            raise IndexError

    except IndexError:
        response.append(build_response_message(107,"Occupancy field"
                                                       " does not match existing record."))
        return [iuser,imagic, response]

    # Check if there exists a matched undo

    time_add = do_database_fetchall(f"SELECT time FROM traffic WHERE locationid={location} AND"
        f" type={vtype} AND occupancy={occupancy} AND sessionid={sessionid} AND mode={1}")
    time_undo = do_database_fetchall(f"SELECT time FROM traffic WHERE locationid={location} AND"
        f" type={vtype} AND occupancy={occupancy} AND sessionid={sessionid} AND mode={-1}") or ()

    if sorted(time_add) == sorted(time_undo):
        response.append(build_response_message(108, "Record matches an existing undo."))
        return [iuser, imagic, response]

    time_diff = [_ for _ in time_add if _ not in time_undo]

    # Check for repeated timestamp

    if time_diff == []:
        time_diff = list((Counter(time_add) - Counter(time_undo)).elements())

    undo_query = (f"INSERT INTO traffic (recordid, sessionid, time, type, locationid, occupancy"
        f",mode) VALUES (NULL,{sessionid},{time_diff[0][0]},{vtype},{location},{occupancy},-1)")
    do_database_execute(undo_query)
    loc_result = do_database_fetchone(f"SELECT name FROM locations WHERE locationid={location}")
    response.append(build_response_message(0, "Vehicle removed for " + loc_result[0]))

    response.append(location_response(sessionid))

    return [iuser, imagic, response]

def handle_download_request(iuser, imagic, content):
    """Provide a CSV file of all traffic observations. The data is summarised into
     one row per date and location pair"""

    sessionid = handle_validate(iuser, imagic)
    if sessionid == 0:
        return ['', '', ""]
	# The CSV header line.
    response = ("Date, Location ID, Location Name, Car, Bus, Bicycle, Motorbike,"
                    " Van, Truck, Taxi, Other\n")

	## CODE NEEDED HERE
        ##
        ## Provide one line for each (day, location) pair of all the vehicles
        # of each type observed by any user.
        ## It should be sorted first by day, earliest first. And then by Location ID, lowest first.
        ##

    # Convert time to datetime and sort it

    count_result = do_database_fetchone("SELECT count(*) FROM traffic")
    date_dict = {}
    timestamp_table = []
    date_table = []

    for recordid in range(1, count_result[0]+1):
        row_timestamp = do_database_fetchone(f"SELECT time "
                f"FROM traffic WHERE recordid = {recordid}")[0]
        timestamp_table.append(row_timestamp)
        row_date = datetime.fromtimestamp(row_timestamp).strftime("%Y-%m-%d")
        date_table.append(row_date)

    timestamp_table = sorted(timestamp_table)
    date_table = sorted(date_table)

    # Create a dictionary with date being keys and timestamp being values

    for date in date_table:
        if date not in date_dict:
            indices = [i for i, item in enumerate(date_table) if item == date]
            timestamp_list = []
            for j in indices:
                timestamp_list.append(timestamp_table[j])
            date_dict[date] = timestamp_list

    for key, val in date_dict.items():
        val = tuple(val)
        locationid = do_database_fetchall(f"SELECT locationid from"
                                    f" traffic WHERE time IN {val} ORDER BY locationid")
        loc_check = -1
        for loc in locationid:
            loc = loc[0]
            if loc != loc_check:
                loc_check = loc
                loc_name = str(do_database_fetchone(f"SELECT name FROM locations"
                                                    f" WHERE locationid = {loc}")[0])
                response += (key + "," + str(loc) + "," + loc_name)
                for i in range(1, 9):
                    no_vehicle = str(do_database_fetchone(f"SELECT SUM(mode) FROM "
                        f"traffic WHERE locationid = {loc} AND time IN {val} AND"
                                                          f" type = {i}")[0] or 0)
                    response += ("," + no_vehicle)
                response += ("\n")

    return [iuser, imagic, response]
