#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-
# vim: sw=4 ts=4 expandtab ai
#
# BugzillaSession - handy class to access Bugzilla without XML-RPC 
#
# Copyright (C) 2005-2008 Alexandr D. Kanevskiy
#
# Contact: Alexandr D. Kanevskiy <packages@bifh.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA
#
# $Id$

"""BugzillaSession - Class for access Bugzilla over the network. 
It uses GET/POST interfaces compatible with older Bugzilla 2.x, which doesn't have XML-RPC."""

__revision__ = "r"+"$Revision$"[11:-2]
__all__ = ( 'BugzillaSession', ) 

import pycurl
import urllib
import StringIO
import os
import csv
import types
import re

try:
    # cElementTree in python 2.5
    import xml.etree.cElementTree as ElementTree
except ImportError:
    import cElementTree as ElementTree

def _parse_bug_csv(csv_string):
    """ Parses csv and returns array of dictionaries """
    reader = csv.reader(csv_string.splitlines())
    items = []
    for item in reader:
        items.append(item)
    bug_list = []
    for item in items[1:]:
        tempo = {}
        for (col, coln) in enumerate(items[0]):
            if coln == '':
                continue
            tempo[coln] = item[col]
        bug_list.append(tempo)
    return bug_list

def _parse_bug_xml(bug_xml, convert_unprintable=True):
    """ 
        Parses bug xml and returns ElementTree obj
        If convert_unprintable is True (default), it converts all unprintable
        characters to '?'. Otherwise tries to parse bug_xml as is.
    """
    try:
        if convert_unprintable:
            import string
            tree = ElementTree.fromstring("".join([sym in string.printable and sym or "?" for sym in bug_xml]))
        else:
            tree =  ElementTree.fromstring(bug_xml)
    except SyntaxError, ex: 
        raise SyntaxError, "Error parsing bug xml: %s" % ex
    
    bug = tree.find("bug")
    if bug.get('error'):
        raise KeyError, "Invalid bug: %s" % bug.get('error') 
    return tree 

def _parse_bug_activity(ba_string):
    """Parses activities from bugzilla bug activity html page"""
    if not ba_string.startswith("<table"):
        # We don't know  how to deal with unknown data
        return None
    try:
        tree =  ElementTree.fromstring(ba_string)
    except SyntaxError, ex: 
        raise SyntaxError, "Error parsing bug activity: %s" % ex
    activity = []
    trs = tree.findall("tr")
    if len(trs) < 2:
        # Strange input. 
        return []
    if trs[0][0].text == "Who":
        # First row is a table header. Skip it
        trs = trs[1:]
    for trw in trs:
        if len(trw) == 5:
            actdict = {
                'who':     trw[0].text.strip(),
                'when':    trw[1].text.strip(),
                'what':    trw[2].text.strip(),
                'removed': trw[3].text.strip(),
                'added':   trw[4].text.strip()
                }
            activity.append(actdict)
        elif len(trw) == 3:
            # line continues for previos action
            actdict = {
                'who':     activity[-1]['who'],
                'when':    activity[-1]['when'],
                'what':    trw[0].text.strip(),
                'removed': trw[1].text.strip(),
                'added':   trw[2].text.strip()
                }
            activity.append(actdict)
        else:
            raise SyntaxError, "Error parsing bug activity. Unknown dataline len: %d" % len(trw)
    return activity       


class BugzillaSession:
    """ 
       Class for access Bugzilla over the network. 
       It uses GET/POST interfaces compatible with older Bugzilla 2.x,
       which doesn't have XML-RPC.
    """
    def __init__(self, baseurl, use_cache=True):
        self._curl = pycurl.Curl()
        self._curl.setopt(pycurl.VERBOSE, False)
        self._curl.setopt(pycurl.SSL_VERIFYPEER, False)
        self._name = None
        self._password = None
        self._login_dict = None
        if use_cache:
            if isinstance(use_cache, types.DictType):
                self._bug_cache = use_cache
            else:
                self._bug_cache = {}
        else: 
            self._bug_cache = None
        if baseurl.endswith(".cgi"):
            self._baseurl = os.path.dirname(baseurl)
        else:
            self._baseurl = baseurl

    def set_login_info(self, name, password, http_auth=True):
        """saves auth info (Bugzilla and http auth)"""
        self._name = name
        self._password = password
        self._login_dict = {'Bugzilla_login': name, 'Bugzilla_password': password }
        if http_auth:
            self._curl.setopt(pycurl.USERPWD, "%s:%s" % (name, password))
            self._curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_ANY)

    def set_proxy(self, proxy_url):
        """Enables proxy support"""
        self._curl.setopt(pycurl.PROXY, proxy_url)

    def fetch_bug_xml(self, bugid, xml_def_encoding = 'iso-8859-1', attachments = True, attachmentdata = False, asunicode = False):
        """Fetch bug xml data from server or from cache, if enabled"""
        if not asunicode and self._bug_cache is not None:
            if self._bug_cache.has_key(str(bugid)):
                return self._bug_cache[str(bugid)]
        reqdict = {'id': str(bugid).strip(), 'ctype': 'xml'}
        if self._login_dict:
            reqdict.update(self._login_dict)
        if not attachments:
            reqdict['excludefield'] = 'attachment'
        elif not attachmentdata:
            reqdict['excludefield'] = 'attachmentdata'
        _result = StringIO.StringIO()
        self._curl.setopt(pycurl.URL, os.path.join(self._baseurl, "show_bug.cgi"))
        self._curl.setopt(pycurl.POST, 1)
        self._curl.setopt(pycurl.POSTFIELDS, urllib.urlencode(reqdict))
        self._curl.setopt(pycurl.WRITEFUNCTION, _result.write)
        self._curl.perform()
        #print self._curl.getinfo(pycurl.HTTP_CODE), self._curl.getinfo(pycurl.EFFECTIVE_URL)
        if self._curl.getinfo(pycurl.HTTP_CODE) != 200:
            return ""
        else:
            result = _result.getvalue()
            if result.find(' encoding="', 0, 100) < 0:
                # Hack for broken bugzilla xml output
                result = result.replace('<?xml version="1.0" standalone="yes"', \
                                '<?xml version="1.0" encoding="%s" standalone="yes"' % xml_def_encoding)

            if self._bug_cache is not None:
                self._bug_cache[str(bugid)] = result

            if asunicode:
                match = re.search(r'<?xml.+\sencoding="(?P<enc>[a-zA-Z0-9:._-]+?)".+?>', result)
                if match:
                    result = result.replace(' encoding="%s"' % match.group('enc'), "", 1)
                result = unicode(result, match.group('enc'))
            return result

    def comment_bugs(self, bugs, comment):
        """Put comment on bugs"""
        __comment = comment.strip()
        if not __comment:
            return "Comment must not be empty"
        else:
            return self.update_bugs(bugs, {'comment': __comment})

    def update_bugs(self, bugs, params = None):
        """
            Group update operation for bugs.
            Possible bugs specifications:
                 id -- single bug id (integer)
                 [id,id,id] or (id,id,id) -- List of bug IDs
                 "id,id,id" -- List of bugs, alternative way (string)
            params should be non-empty dictionary with valid bugzilla update form fields
        """
        reqdict = { 'dontchange': 'dont_change',
                    'product': 'dont_change',
                    'version': 'dont_change',
                    'component': 'dont_change',
                    'target_milestone': 'dont_change',
                    'rep_platform': 'dont_change',
                    'priority': 'dont_change',
                    'bug_severity': 'dont_change',
                    'bug_file_loc': 'dont_change',
                    'short_desc': 'dont_change',
                    'op_sys': 'dont_change',
                    'longdesclength': 'dont_change',
                    'qa_contact': 'dont_change',
                    'featdev': 'dont_change',
                    'keywords': '',
                    'keywordaction': 'add',
                    'knob': 'none' }
        if isinstance(params, types.DictType) and params:
            reqdict.update(params)
        else:
            return "Not valid params dictionary"
        if self._login_dict:
            reqdict.update(self._login_dict)

        if isinstance(bugs, (types.ListType, types.TupleType)):
            # List of bugs
            lbugs = bugs
        elif isinstance(bugs, basestring):
            # String ? Hmm, assume as list of bugs separated by ','
            lbugs = re.split("\s*,\s*", bugs)
        elif isinstance(params, types.IntType):
            # Just one bug id
            lbugs = [ str(bugs) ]
        for bug in lbugs:
            reqdict['id_' + str(bug)] = str(bug)
        _result = StringIO.StringIO()
        self._curl.setopt(pycurl.URL, os.path.join(self._baseurl, "process_bug.cgi"))
        self._curl.setopt(pycurl.POST, 1)
        self._curl.setopt(pycurl.POSTFIELDS, urllib.urlencode(reqdict))
        self._curl.setopt(pycurl.WRITEFUNCTION, _result.write)
        self._curl.perform()
        #print self._curl.getinfo(pycurl.HTTP_CODE), self._curl.getinfo(pycurl.EFFECTIVE_URL)
        if _result.getvalue().find("<title>Internal Error</title>") >= 0:
            return _result.getvalue()
        if self._curl.getinfo(pycurl.HTTP_CODE) != 200:
            return _result.getvalue()
        else:
            return ""

    def drop_cache_for_bug(self, bug):
        """ Removes information about bug from internal cache """
        if self._bug_cache is not None:
            if self._bug_cache.has_key(str(bug)):
                del self._bug_cache[str(bug)]
            else:
                raise KeyError, "Bug %s not present in cache" % bug
        else:
            raise KeyError, "Cache not enabled"

    def fetch_buglist_csv(self, params):
        """ 
            Fetches csv from buglist.cgi.
                Possible parameters:
                    id -- single bug id (integer)
                    [id,id,id] or (id,id,id) -- List of bug IDs
                    "id,id,id" -- List of bugs, alternative way (string)
                    {'bugzilla_internal_param1': 'value',...} -- advanced parameters to request
        """
        reqdict = { 
                    'ctype': 'csv',
                    'columnlist': 'all'}
        if self._login_dict:
            reqdict.update(self._login_dict)
        if isinstance(params, (types.ListType, types.TupleType)):
            # List of bugs
            reqdict['bug_id'] = ",".join([str(bug) for bug in params])
        elif isinstance(params, basestring):
            # String ? Hmm, assume as list of bugs separated by ','
            reqdict['bug_id'] = params
        elif isinstance(params, types.IntType):
            # Just one bug id
            reqdict['bug_id'] = str(params)
        elif isinstance(params, types.DictType):
            # Some advanced query
            reqdict.update(params)
        else:
            return ""
        _result = StringIO.StringIO()
        self._curl.setopt(pycurl.URL, os.path.join(self._baseurl, "buglist.cgi"))
        self._curl.setopt(pycurl.POST, 1)
        self._curl.setopt(pycurl.POSTFIELDS, urllib.urlencode(reqdict))
        self._curl.setopt(pycurl.WRITEFUNCTION, _result.write)
        self._curl.perform()
        #print self._curl.getinfo(pycurl.HTTP_CODE), self._curl.getinfo(pycurl.EFFECTIVE_URL)
        #print self._result.getvalue()
        if self._curl.getinfo(pycurl.HTTP_CODE) == 200:
            return _result.getvalue()
        else:
            return ""

    def fetch_bug_xml_tree(self, bug):
        """ Return ElementTree parsed tree object """
        return _parse_bug_xml(self.fetch_bug_xml(bug))

    def fetch_buglist_info(self, params):
        """ Return small info about bugs """
        return _parse_bug_csv(self.fetch_buglist_csv(params))

    def showbug_url(self, bug):
        """ Returns link to showbug.cgi, with a parameter of bug """
        if isinstance(bug, (types.ListType, types.TupleType)):
            return [self.showbug_url(obg) for obg in bug]
        else:
            return os.path.join(self._baseurl, "show_bug.cgi?id=%s" % urllib.quote(str(bug)))

    def fetch_bug_activity(self, bugid):
        """Fetch bug activity data from server. Returns parsed data"""
        return _parse_bug_activity(self.__get_bug_activity_table(bugid))

    def __get_bug_activity_table(self, bugid):
        """Raw function to get bug activity table"""
        reqdict = {'id': str(bugid).strip()}
        if self._login_dict:
            reqdict.update(self._login_dict)
        _result = StringIO.StringIO()
        self._curl.setopt(pycurl.URL, os.path.join(self._baseurl, "show_activity.cgi"))
        self._curl.setopt(pycurl.POST, 1)
        self._curl.setopt(pycurl.POSTFIELDS, urllib.urlencode(reqdict))
        self._curl.setopt(pycurl.WRITEFUNCTION, _result.write)
        self._curl.perform()
        if self._curl.getinfo(pycurl.HTTP_CODE) != 200:
            return ""
        else:
            result = _result.getvalue()
            match = re.search(r"(?P<act><table.+</table>)", result, re.M+re.DOTALL)
            if not match:
                return ""
            result = match.group("act")
            result = result.replace("&nbsp;"," ")
            # Ugly bug workarround
            result = result.replace("<table border ","<table ")
            # We also don't want to have references
            result = re.subn(r'(?sm)<a href=".+">(.+)</a>', r'\1', result)[0]
            return result

