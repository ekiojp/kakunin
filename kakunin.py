#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import re
import argparse
import sqlite3
import requests
import json
import getpass

# Me
__author__ = "Emilio / @ekio_jp"
__version__ = "1.0"

# Config
motd = 'motd-kakunin.txt'
tlpcnt = 0


def connectsql(sqlfile):
    conn = sqlite3.connect(sqlfile)
    c = conn.cursor()
    return conn, c


def closesql(conn):
    conn.close()


def getxploit(c, cve):
    xploit = []
    for x in range(len(cve)):
        cveqry = 'SELECT exploitdbid FROM map_cve_exploitdb WHERE cveid=?'
        c.execute(cveqry, [cve[x]])
        result = c.fetchone()
        if result:
            xploit.append('https://www.exploit-db.com/exploits/' + str(result[0]))
    return xploit


def parsingopt():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', dest='dryrun', action='store_true', help='Dry-run TEST')
    parser.add_argument('-w', dest='ws_name', required=True, metavar='<workspace>',
                        default='test', help='Faraday Workspace')
    parser.add_argument('-s', dest='server', required=False, metavar='<server>',
                        default='http://localhost:5985', help='Faraday Server (default: http://localhost:5985)')
    parser.add_argument('-i', dest='vfeed', required=True, metavar='<vfeed.db>',
                        help='vfeed.db by https://github.com/toolswatch/vFeed')
    parser.add_argument('-u', dest='username', required=False, metavar='<username>',
                        default='faraday', help='Faraday Username (default: faraday)')
    parser.add_argument('-p', dest='password', required=False, metavar='<password>',
                        help='Faraday Password (default: prompt)')
    if len(sys.argv) > 1:
        try:
            return parser.parse_args()
        except IOError, msg:
            parser.error(str(msg))
    else:
        with open(motd, 'r') as sfile:
            print(sfile.read())
        print('Author: ' + __author__)
        print('Version: ' + __version__ + '\n')
        parser.print_help()
        sys.exit(1)


# Main Function
def main():
    # Get options
    options = parsingopt()
    ws_name = options.ws_name
    server_address = options.server
    fdvfeed = options.vfeed
    username = options.username
    if options.password:
        password = options.password
    else:
        password = getpass.getpass()

    # API Login
    session = requests.Session()
    ap = session.post(server_address + '/_api/login', json={'email': username, 'password': password})
    if ap.status_code != 200:
        print('ERROR: Faraday API credentials invalid')
        sys.exit(1)

    # Grab all Vuls from Workspace
    resp = session.get(server_address + '/_api/v2/ws/' + ws_name + '/vulns/')
    data = resp.json()

    # Connect to SQLite
    try:
        vfeedconn, csqlvfeed = connectsql(fdvfeed)
    except Exception as error:
        print('ERROR: Can\'t connect to vFeed SQLite file: ', fdvfeed)
        print(error)

    # Search for CVE's on each Vul Refs and lookup ExpoitDB
    refupdated = 0
    for x in range(len(data['vulnerabilities'])):
        cveset = set()
        for z in range(len(data['vulnerabilities'][x]['value']['refs'])):
            cveref = re.findall('CVE\-\d+\-\d+', data['vulnerabilities'][x]['value']['refs'][z])
            if cveref:
                map(cveset.add, cveref)
        uniqcve = list(cveset)
        refs = getxploit(csqlvfeed, uniqcve)
        if refs:
            vu = data['vulnerabilities'][x]['value']
            for l in range(len(refs)):
                vu['refs'].append(refs[l])
            vu['confirmed'] = True
            if not options.dryrun:
                mm =  session.put(server_address + '/_api/v2/ws/' + ws_name + '/vulns/' + str(data['vulnerabilities'][x]['key']) + '/', json=vu)
                if mm.status_code != 200:
                    print('ERROR: Updating Vul: ', data['vulnerabilities'][x]['value']['name'])
                    print(mm.text)
            else:
                print('TEST: Updating Reference for Vul: ', data['vulnerabilities'][x]['value']['name'])
            refupdated = refupdated + 1

    closesql(vfeedconn)

    if not options.dryrun:
        print('Amount of Vulnerabilities in Workspace: ', len(data['vulnerabilities']))
        print('Confirm Vuls and Reference Updated: ', refupdated)


# Call main
if __name__ == '__main__':
    main()
