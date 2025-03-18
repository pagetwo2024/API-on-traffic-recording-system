#!/usr/bin/env python
"""Backend server for traffic record database."""

# This is a simple web server for a traffic counting application.
# It's your job to extend it by adding the missing backend functionality
# You should only need to extend this file. The client side code
# (html, javascript and css) is complete and does not require editing
# or detailed understanding.

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

### Database access wrappers

def do_database_execute(command):
    """Execute an SQL command that is not expected to return any rows."""
    print(command)
    try:
        database = sqlite3.connect('database.db') # DO NOT CHANGE THE NAME OF THE DATABASE
        cursor = database.cursor()
        cursor.execute(command)
        database.commit()
    except Exception as error:
        database.rollback()
    finally:
        database.close()

def do_database_fetchone(command):
    """Execute an SQL command that returns at most a single row."""
    print(command)
    try:
        database = sqlite3.connect('database.db') # DO NOT CHANGE THE NAME OF THE DATABASE
        cursor = database.cursor()
        cursor.execute(command)
        result = cursor.fetchone()
        print(result)
        database.close()
        return result
    except Exception as error:
        print(error)
        return None

def do_database_fetchall(command):
    """Execute an SQL command that can return any number of rows, including none."""
    print(command)
    try:
        database = sqlite3.connect('database.db') # DO NOT CHANGE THE NAME OF THE DATABASE
        cursor = database.cursor()
        cursor.execute(command)
        result = cursor.fetchall()
        print(result)
        database.close()
        return result
    except Exception as error:
        print(error)
        return None


### The following build_ functions return the responses that the front end client understands.
### You can user these to build a list of responses

def build_response_message(code, text):
    """This function builds a message response that displays a meexample1.dbssage
       to the user on the web page. It also returns an error code."""
    return {"type":"message","code":code, "text":text}

def build_response_vcount(vtype,total):
    """This function builds a summary response for a vehicle type"""
    return {"type":"vcount", "vtype":vtype, "count":total}

def build_response_location(locationid, name):
    """This function builds an activity response that contains the id and name of an
     activity type,"""
    return {"type":"location", "id":locationid, "name":name}

def build_response_total(total):
    """The number of vehicles that have been seen in this session."""
    return {"type":"total", "total":total}

def build_response_redirect(where):
    """This function builds the page redirection response
       It indicates which page the client should fetch.
       If this action is used, it should be the only response provided."""
    return {"type":"redirect", "where":where}

### Some utility code

def random_digits(size):
    """Return a random string of digits of size n"""
    range_start = 10**(size-1)
    range_end = (10**size)-1
    return random.randint(range_start, range_end)

def timestamp():
    """Return number of seconds since the start of the epoch"""
    return int(time.time())

def location_response(sessionid):
    """Work out how many vehicles we've seen in this session, regardless of location."""
    tot_query = f"SELECT sum(mode) FROM traffic WHERE sessionid = {sessionid} GROUP BY sessionid"
    total = do_database_fetchone(tot_query)
    if total:
        return build_response_total(total[0])
    return build_response_total(0)

def handle_validate(iuser, imagic):
    """Check if the supplied userid and magic match a currently active session
    and return the sessionid if they do, otherwise 0"""
    result = do_database_fetchone('SELECT * FROM session WHERE session.end=0 AND '
                                'session.userid="'+iuser+'" AND session.magic="'+imagic+'"')
    if result is not None:
        return result[0]
    return 0 #not a valid sessionid

### The main command handler functions. The are the functions invoked when the json requests
### includes a specific command.

def handle_login_request(iuser, imagic, content):
    """Deal with a login request"""
    response = []

    if 'username' in content and 'password' in content:
        username = content['username']
        password = content['password']

        # Check if the username and password match in the database
        user_query = (f"SELECT * FROM users WHERE username = '{username}' "
                      f"AND password = '{password}'")
        user_result = do_database_fetchone(user_query)

        if user_result:
            # Generate a random magic identifier for the session
            magic = str(random_digits(8)) #we should really test its not present.
            start = timestamp()

            # close any existing sessions but updating any zero end times to the current time
            end_query = (f"UPDATE session SET end = {start} "
                         f"WHERE userid = {user_result[0]} AND end=0")
            do_database_execute(end_query)

            # Create a new session record in the session table
            session_query = (f"INSERT INTO session (sessionid, userid, magic,start,end) VALUES "
                             f"(NULL, {user_result[0]}, '{magic}',{start},0)")
            do_database_execute(session_query)

            # Return user details and the generated magic identifier
            response.append(build_response_redirect('/index.html'))

            iuser = user_result[0] if user_result else ''
            imagic = magic if user_result else ''
        else:
            response.append(build_response_message(103, 'Invalid credentials. One or both of '
                                                'Username and Password are incorrect or empty.'))
            return ['','', response]
    else:
        response.append(build_response_message(200, 'Missing username or '
                                                    'password field in request.'))
        return ['','', response]

    return [iuser, imagic, response]

def handle_logout_request(iuser, imagic, parameters):
    """Deal with a logout request"""
    response = []
    if imagic and iuser :
        end = timestamp()
        # End the user's session by removing the session record
        end_query = (f"UPDATE session SET end={end} WHERE userid = {iuser}"
                     f" AND magic='{imagic}' AND end=0")
        do_database_execute(end_query)

        # Return a message indicating successful logout
        response.append(build_response_redirect('/logout.html'))
        # Redirect to the index page after logout
    else:
        response.append(build_response_message(110, 'User is not logged in'))


    return ['', '', response]

def handle_location_request(iuser, imagic, content):
    """Return a list of current locations."""
    response = []
    sessionid = handle_validate(iuser, imagic)
    if sessionid == 0:
        response.append(build_response_redirect('/login.html'))
        return ['', '', response]
    loc_query = "SELECT * FROM locations ORDER BY locationid"
    locs = do_database_fetchall(loc_query)

    for loc in locs:
        response.append(build_response_location(loc[0],loc[1]))

    response.append(location_response(sessionid))

    return [iuser, imagic, response]


## The user has requested a vehicle be added to the count
## content['location'] the location to be recorded
## content['occupancy'] the occupant count to be recorded
## content['type'] the type to be recorded
## Return the username, magic identifier (these may be empty strings) and the response action set.
def handle_add_request(iuser, imagic, content):
    """Adds a vehicle to the traffic record."""
    response  = []


    sessionid = handle_validate(iuser, imagic)
    if sessionid == 0:
        response.append(build_response_redirect('/login.html'))
        return ['', '', response]
    if sessionid != 0:
        ## a valid session so process the addition of the entry.
        # First check that all the arguments are present

        try:
            location = content['location']
        except:
            response.append(build_response_message(201,"Location field missing from request."))
            return [iuser,imagic, response]

        try:
            vtype = content['type']
        except:
            response.append(build_response_message(202,"Type field missing from request."))
            return [iuser,imagic, response]

        try:
            occupancy = content['occupancy']
        except:
            response.append(build_response_message(203,"Occupancy field missing from request."))
            return [iuser,imagic, response]

        # Then check that they are valid values
        try:
            location = int(location)

            loc_query = f"SELECT * FROM locations WHERE locationid = {location}"
            loc_result = do_database_fetchone(loc_query)
            location = loc_result[0] # should fail if we couldn't find it.

        except:
            response.append(build_response_message(101,"Location field invalid."))
            return [iuser,imagic, response]

        try:
            vtype = int(vtype)
            if vtype<1 or vtype>8:
                raise Exception("Out of range")
        except:
            response.append(build_response_message(102,"Type field invalid."))
            return [iuser,imagic, response]

        try:
            occupancy = int(occupancy)
            if occupancy<1 or occupancy>4:
                raise Exception("Out of range")
        except:
            response.append(build_response_message(103,"Occupancy field invalid."))
            return [iuser,imagic, response]

    # Everything looks good, so add the record

    now = timestamp()
    add_query = (f"INSERT INTO traffic (recordid, sessionid, time, type, locationid, occupancy,"
                 f" mode) VALUES (NULL, {sessionid},{now},{vtype},{location},{occupancy},1)")
    do_database_execute(add_query)
    response.append(build_response_message(0,"Vehicle added for "+loc_result[1]))

    # Work out how many vehicles we've seen in this session, regardless of location.
    response.append(location_response(sessionid))

    return [iuser,imagic,response]

## The user has requested a vehicle be undone from the count
## content['location'] the location to be undone
## content['occupancy'] the occupant count to be undone
## content['type'] the type to be undone
## Return the username, magic identifier (these may be empty  strings) and the response action set.

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


def handle_summary_request(iuser,imagic,content):
    """This code handles a request for update to the session summary values."""
    response = []
    sessionid = handle_validate(iuser, imagic)
    if sessionid == 0:
        response.append(build_response_redirect('/login.html'))
        return ['','',response]
    if sessionid != 0:

        try:
            location = content['location']
        except:
            response.append(build_response_message(201,"Location field missing from request."))
            return [iuser,imagic, response]

        try:
            location = int(location)

            loc_query = f"SELECT * FROM locations WHERE locationid = {location}"
            loc_result = do_database_fetchone(loc_query)
            location = loc_result[0] # should fail if we could n't find it.

        except:
            response.append(build_response_message(101,"Location field invalid."))
            return [iuser,imagic, response]

        for loop in range(1,9):

            result = do_database_fetchone(f"SELECT SUM(mode) FROM traffic WHERE sessionid="
                        f"{sessionid} AND type={loop} AND locationid = {location}")
            if result[0]:
                response.append(build_response_vcount(loop, result[0]))
            else:
                response.append(build_response_vcount(loop, 0))

        response.append(build_response_message(0, f"Summary compiled for {loc_result[1]}."))

    return [iuser,imagic,response]


class myHTTPServer_RequestHandler(BaseHTTPRequestHandler):
    "This class is extended to include new post and get request handlers"

    # POST This function responds to GET requests to the web server.
    def do_POST(self):
        "The set_cookies function adds/updates two cookies returned with a webpage."
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(item, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            item.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            item.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            "This function returns the values of the user and magic cookies if they exist"
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        print(user_magic)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # The special file 'action' is not a real file, it indicates an action
        # we wish the server to execute.
        if parsed_path.path == '/action':
            self.send_response(200) #respond that this is a valid page request

            # extract the content from the POST request.
            # This are passed to the handlers.
            length =  int(self.headers.get('Content-Length'))
            scontent = self.rfile.read(length).decode('ascii')
            print(scontent)
            if length > 0 :
                content = json.loads(scontent)
            else:
                content = []

            # deal with get parameters
            parameters = urllib.parse.parse_qs(parsed_path.query)

            if 'command' in content:
                # check if one of the parameters supplied was 'command'
                # If it is, identify which command and call the appropriate handler function.
                # You should not need to change this code.
                if content['command'] == 'login':
                    [user, magic, response] = handle_login_request(user_magic[0],
                                                                   user_magic[1], content)
                    #The result of a login attempt will be to set the
                    # cookies to identify the session.
                    set_cookies(self, user, magic)
                elif content['command'] == 'logout':
                    [user, magic, response] = handle_logout_request(user_magic[0],
                                                                    user_magic[1], content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif content['command'] == 'add':
                    [user, magic, response] = handle_add_request(user_magic[0],
                                                                 user_magic[1], content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif content['command'] == 'undo':
                    [user, magic, response] = handle_undo_request(user_magic[0],
                                                                  user_magic[1], content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif content['command'] == 'summary':
                    [user, magic, response] = handle_summary_request(user_magic[0],
                                                                     user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif content['command'] == 'location':
                    [user, magic, response] = handle_location_request(user_magic[0],
                                                                      user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                else:
                    # The command was not recognised, report that to the user. This uses a
                    # special error code that is not part of the codes you will use.
                    response = []
                    response.append(build_response_message(901,
                                                        'Internal Error: Command not recognised.'))

            else:
                # There was no command present, report that to the user. This uses a special
                # error code that is not part of the codes you will use.
                response = []
                response.append(build_response_message(902,'Internal Error: Command not found.'))

            text = json.dumps(response)
            print(text)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(text, 'utf-8'))

        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404) # a file not found html response
            self.end_headers()

   # GET This function responds to GET requests to the web server.
   # You should not need to change this function. It deals with all files
    # except /download.csv for which it invokes
   # handle_download_request() which your are responsible for completing.
    def do_GET(self):
        "GET This function responds to GET requests to the web server."

        # The set_cookies function adds/updates two cookies returned with a webpage.
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(item, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            item.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            item.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # Return a CSS (Cascading Style Sheet) file.
        # These tell the web client how the page should appear.
        if self.path.startswith('/css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())

        # Return a Javascript file.
        # These contain code that the web client can execute.
        elif self.path.startswith('/js'):
            self.send_response(200)
            self.send_header('Content-type', 'text/js')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())

        # A special case of '/' means return the index.html (homepage)
        # of a website
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./pages/index.html', 'rb') as file:
                self.wfile.write(file.read())

        # Return html pages.
        elif parsed_path.path.endswith('.html'):
            try:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('./pages'+parsed_path.path, 'rb') as file:
                    self.wfile.write(file.read())
            except:
                # The names file has not been found
                self.send_response(404)
                self.end_headers()

        # We also provide a special downloaded csv file.
        elif parsed_path.path == '/download.csv':
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.end_headers()
            [user, magic, response] = handle_download_request(user_magic[0], user_magic[1], '')
            self.wfile.write(bytes(response, 'utf-8'))
        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404)
            self.end_headers()


def run():
    """This is the entry point function to this code."""
    print('starting server...')
    ## You can add any extra start up code here
    # Server settings
    # When testing you should supply a command line argument in the 8081+ range

    # Changing code below this line may break the test environment.
    # There is no good reason to do so.
    if len(sys.argv)<2: # Check we were given both the script name and a port number
        print("Port argument not provided.")
        return
    server_address = ('127.0.0.1', int(sys.argv[1]))
    httpd = HTTPServer(server_address, myHTTPServer_RequestHandler)
    print('running server on port =',sys.argv[1],'...')
    httpd.serve_forever() # This function will not return until the server is aborted.

run()
