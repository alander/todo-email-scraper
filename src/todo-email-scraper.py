#!/usr/bin/env python

#  todo-email-scraper.py - Scrape TODOs from an email address and add them to an org file
#
# Copyright (c) 2014 Free Software Foundation, Inc.
#
# Authors:
#          Anthony Lander <anthony.lander@gmail.com>
#
# Version: 1.0
# Keywords: org, todo, email
#
# This file is not part of GNU Emacs.
#
# This program is free software# you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation# either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY# without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
# Commentary:
#
# - Email subject is the TODO line, and body is the TODO body.
# - Add a property line :TODO-TARGET: true to the parent heading where TODOs should be dropped
# - Configure email address, diary file, password below.
# - You can schedule this to run, say, every 30 minutes in a cron job.

# - The scraper scrapes all emails from a designated address (so only you can
# - send yourself todos). as such, it is best to set up a todo email address to
# - receive only todo emails.

import sys
from os import rename
from datetime import datetime
import imaplib
from io import StringIO
from email.parser import Parser
from configobj import ConfigObj
from pkg_resources import resource_string
import ipdb

config_filename = 'todo-email-scraper.rc'
server = ''
username = ''
password = ''
diary_file = ''
authorized_senders = ()
todo_target_property_line = ''
todo_subject_keywords = ()


def is_diary_file_available():
    try:
        file = open(diary_file, "r", encoding='UTF-8')
    except IOError:
        return False
    file.close()
    return True

    
def get_todos():
    """Read all todo emails and mark them as read. Parse the emails and return a
    list of todos

    """

    imap = imaplib.IMAP4_SSL(server)
    imap.login(username, password)
    imap.select()

    search_criteria = imap_search_criteria()
    part_type, data = imap.search(None, search_criteria)

    todos = []

    for num in data[0].split():
        todo_subject = ''
        todo_body = []
        part_type, data = imap.fetch(num, '(RFC822)')

        file = StringIO(data[0][1].decode(encoding='UTF-8'))
        message = Parser().parse(file)

        todo_subject = message['subject']
        body = ''

        for part in message.walk():
            part_type = part.get_content_type()
            if part_type and part_type.lower() == "text/plain":
                # Found the first text/plain part
                body = part.get_payload(decode=True)
                break
        
        long_line = ""
        for line in [line.strip() for line in body.splitlines() if len(line) > 0]:
            if line[-1:] == "=":
                long_line += line[:-1]
            else:
                if len(long_line) > 0:  # There is a long line waiting to be written
                    todo_body.append(long_line)
                    long_line = ""
                else:
                    todo_body.append(line)
                    long_line = ""
                
        if len(long_line) > 0:
            todo_body.append(long_line)

        if is_subject_todo_keyword(todo_subject):
            todo_subject = todo_body[0]
            todo_body = ''
            
        todos.append({'subject': todo_subject, 'body': todo_body})
                
    imap.close()
    imap.logout()
    return todos
    

def is_subject_todo_keyword(todo_subject):
    """True if the subject is one of the magic TODO keywords"""

    return todo_subject.lower() in todo_subject_keywords
        

def imap_search_criteria():
    """Answer an IMAP search string to search for unseen emails from any authorized sender

    """
   
    search_criteria = 'UNSEEN FROM "' + authorized_senders[0] + '"'
    for each in authorized_senders[1:]:
        search_criteria = 'OR (' + search_criteria + ') (UNSEEN FROM "' + each + '")'

    return "(" + search_criteria + ")"

    
def new_diary_lines_with_todos(todos):
    """Read the diary file, adding in todos at the appropriate place.
    Return a list of diary lines.
    """
    
    try:
        file = open(diary_file, "rt+", encoding='UTF-8')
        found = False
        done = False
        stars = ""
        timestamp = datetime.now().strftime("[%Y-%m-%d %a %H:%M]")
        logbook_lines = [":LOGBOOK:", '- State "TODO"       from ""           ' + timestamp, ":END:"]
        
        lines = []
        while not done:
            line = file.readline()
            if len(line) == 0:
                done = True
            else:
                lines.append(line)

                if not found:
                    if line[0] == "*":
                        stars = line.split()[0]

                    if line.strip().lower() == todo_target_property_line:
                        found = True

                        line = ""
                        while not line.strip().lower() == ":end:":
                            line = file.readline()
                            lines.append(line)


                        stars = stars + "** "  # Indent one more under the todo target heading
                        for todo in todos:
                            line = "%s%s%s%s" % (stars, "TODO ", todo['subject'].decode('UTF-8'), "\n")
                            lines.append(line)
                            spaces = stars.replace("*", " ")
                            for line in logbook_lines:
                                lines.append(spaces + line + "\n")

                            for line in todo['body']:
                                lines.append(spaces + line.decode('UTF-8') + "\n")
        file.close()
    except:
        print("Unexpected error: {}".format(sys.exc_info()[0]))
        file.close()
        raise
    return lines


def write_new_diary(filename, diary_lines):
    try:
        file = open(filename, "w", encoding='UTF-8')
        for line in diary_lines:
            file.write(line)
        file.close()
        return True
    except:
        print("Unexpected error: {}".format(sys.exc_info()[0]))
        file.close()
        raise

    return False


def scrape_todos():
    parse_config(config_filename)

    if not is_diary_file_available():
        print("No diary file available - aborting.")
        sys.exit(-1)

    todos = get_todos()
    if len(todos) > 0:
        diary_lines = new_diary_lines_with_todos(todos)
        try:
            now = datetime.now().strftime(".%Y-%m-%d-%H-%M")
            diary_backup = diary_file + now + ".orig"
            rename(diary_file, diary_backup)
        except:
            print("Unexpected error while renaming: {}".format(sys.exc_info()[0]))
            raise
        
        write_new_diary(diary_file, diary_lines)
        print("Added ", len(todos), " todos at ", now)


def parse_config(filename):
    global server, username, password, authorized_senders
    global diary_file, todo_target_property_line, todo_subject_keywords
    
    config = ConfigObj(filename)

    server = config['email']['server']
    username = config['email']['username']
    password = config['email']['password']
    authorized_senders = config['email']['authorized_senders']

    diary_file = config['org']['diary_file']
    todo_target_property_line = config['org']['todo_target_property_line']
    todo_subject_keywords = config['org']['todo_subject_keywords']
    

def run():
    global config_filename

    if len(sys.argv) > 1:       # Config file
        config_filename = sys.argv[1]

    scrape_todos()

    
if __name__ == '__main__':
    run()
    sys.exit(0)
