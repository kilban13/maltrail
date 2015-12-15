#!/usr/bin/env python

"""
Copyright (c) 2014-2015 Miroslav Stampar (@stamparm)
See the file 'LICENSE' for copying permission
"""

import os
import re
import socket
import stat
import subprocess

from core.attribdict import AttribDict

config = AttribDict()
trails = {}

NAME = "Maltrail"
VERSION = "0.8.157"
SERVER_HEADER = "%s/%s" % (NAME, VERSION)
DATE_FORMAT = "%Y-%m-%d"
ROTATING_CHARS = ('\\', '|', '|', '/', '-')
TIMEOUT = 30
FRESH_IPCAT_DELTA_DAYS = 10
USERS_DIR = os.path.join(os.path.expanduser("~"), ".%s" % NAME.lower())
TRAILS_FILE = os.path.join(USERS_DIR, "trails.csv")
IPCAT_CSV_FILE = os.path.join(USERS_DIR, "ipcat.csv")
IPCAT_SQLITE_FILE = os.path.join(USERS_DIR, "ipcat.sqlite")
IPCAT_URL = "https://raw.github.com/client9/ipcat/master/datacenters.csv"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
HTTP_DEFAULT_PORT = 8338
HTTP_TIME_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"  # Reference: http://stackoverflow.com/a/225106
SNAP_LEN = 2000
BLOCK_LENGTH = 1 + 2 + 4 + 4 + SNAP_LEN  # primitive mutex + short for packet size + int for sec + int for usec + max packet size
BUFFER_LENGTH = 512 * 1024 * 1024 / BLOCK_LENGTH * BLOCK_LENGTH  # 512MB buffer
SHORT_SENSOR_SLEEP_TIME = 0.00001
REGULAR_SENSOR_SLEEP_TIME = 0.001
LOAD_TRAILS_RETRY_SLEEP_TIME = 60
UNAUTHORIZED_SLEEP_TIME = 5
NO_SUCH_NAME_PER_HOUR_THRESHOLD = 30
NO_BLOCK = -1
END_BLOCK = -2
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_DIR = os.path.join(ROOT_DIR, "html")
ETH_LENGTH = 14
PPPH_LENGTH = 4
CONFIG_FILE = os.path.join(ROOT_DIR, "maltrail.conf")
SYSTEM_LOG_DIR = "/var/log" if not subprocess.mswindows else "C:\\Windows\\Logs"
DEFAULT_LOG_PERMISSIONS = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
HOSTNAME = socket.gethostname()
DISABLED_CONTENT_EXTENSIONS = (".py", ".pyc", ".md", ".txt", ".bak", ".conf", ".zip", "~")
LOW_PRIORITY_INFO_KEYWORDS = ("reputation", "attacker", "spammer", "abuser", "malicious", "dnspod", "crawler", "compromised")
HIGH_PRIORITY_REFERENCES = ("bambenekconsulting.com", "(custom)",)
BAD_TRAIL_PREFIXES = ("127.", "192.168.", "localhost")
SUSPICIOUS_DIRECT_DOWNLOAD_EXTENSIONS = set((".apk", ".exe", ".scr"))
SUSPICIOUS_FILENAMES = set(("gate.php",))
SUSPICIOUS_HTTP_REQUEST_REGEX = r"(?i)information_schema|\b(AND|OR|SELECT)\b.*/\*.*\*/|/\*.*\*/.*\b(AND|OR|SELECT)\b|\b(AND|OR)[^\w]+\d+['\") ]?[=><]['\"( ]?\d+|(alert|confirm|prompt)\((\d+|document\.|[^\w]*XSS)|\bping -[nc] \d+|floor\(rand\(|ORDER BY \d+|sysdatabases|(\.\./){3,}(?!images)|\bSELECT\b.*\bFROM\b.*\bWHERE\b|\bSELECT \w+ FROM \w+|<script.*?>|\balert\(|xp_cmdshell|/etc/passwd|<\?php|boot\.ini|\bwindows[\\/]win\.ini|\bsleep\(|\bWAITFOR[^\w]+DELAY\b|\bCONVERT\(|VARCHAR|\bUNION\s+(ALL\s+)?SELECT\b"
SUSPICIOUS_HTTP_REQUEST_FORCE_ENCODE_CHARS = "( )"
SUSPICIOUS_UA_REGEX = ""
WHITELIST_HTTP_REQUEST_KEYWORDS = ("fql", "yql", "ads", "../images", "../scripts")
WHITELIST_UA_KEYWORDS = ("62691CB3BF62DAF233FB2C02782E7BD2", "AntiVir-NGUpd", "TMSPS")
WHITELIST_LONG_DOMAIN_NAME_KEYWORDS = ("blog",)
SUSPICIOUS_UA_LENGTH_THRESHOLD = 10
SESSIONS = {}
NO_SUCH_NAME_COUNTERS = {}  # this won't be (expensive) shared in multiprocessing run (hence, the threshold will effectively be n-times higher)
SESSION_ID_LENGTH = 16
SESSION_EXPIRATION_HOURS = 24
IPPROTO_LUT = dict(((getattr(socket, _), _.replace("IPPROTO_", "")) for _ in dir(socket) if _.startswith("IPPROTO_")))
DEFLATE_COMPRESS_LEVEL = 9
PORT_SCANNING_THRESHOLD = 10
SUSPICIOUS_DOMAIN_LENGTH_THRESHOLD = 24
WHITELIST = set()

def _get_total_physmem():
    retval = None

    try:
        if subprocess.mswindows:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong
            class MEMORYSTATUS(ctypes.Structure):
                _fields_ = [
                    ('dwLength', c_ulong),
                    ('dwMemoryLoad', c_ulong),
                    ('dwTotalPhys', c_ulong),
                    ('dwAvailPhys', c_ulong),
                    ('dwTotalPageFile', c_ulong),
                    ('dwAvailPageFile', c_ulong),
                    ('dwTotalVirtual', c_ulong),
                    ('dwAvailVirtual', c_ulong)
                ]

            memory_status = MEMORYSTATUS()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUS)
            kernel32.GlobalMemoryStatus(ctypes.byref(memory_status))

            retval = memory_status.dwTotalPhys
        else:
            retval = 1024 * int(re.search(r"(?i)MemTotal:\s+(\d+)\skB", open("/proc/meminfo").read()).group(1))
    except:
        pass

    if not retval:
        try:
            import psutil

            retval = psutil.phymem_usage().total
        except:
            pass

    return retval

def read_config(config_file):
    global BUFFER_LENGTH
    global config

    if not os.path.isfile(config_file):
        exit("[!] missing configuration file '%s'" % config_file)
    else:
        print "[i] using configuration file '%s'" % config_file

    config.clear()

    try:
        array = None
        content = open(config_file, "rb").read()

        for line in content.split("\n"):
            line = re.sub(r"#.+", "", line)
            if not line.strip():
                continue

            if line.count(' ') == 0:
                array = line.upper()
                config[array] = []
                continue

            if array and line.startswith(' '):
                config[array].append(line.strip())
                continue
            else:
                array = None
                try:
                    name, value = line.strip().split(' ', 1)
                except ValueError:
                    name = line
                    value = ""
                finally:
                    name = name.strip().upper()
                    value = value.strip("'\"").strip()

            if any(name.startswith(_) for _ in ("USE_", "SET_", "CHECK_", "ENABLE_", "SHOW_")):
                value = value.lower() in ("1", "true")
            elif any(name.startswith(_) for _ in ("DISABLE_",)):
                value = value.lower() in ("1", "true")
            elif value.isdigit():
                value = int(value)
            else:
                for match in re.finditer(r"\$([A-Z0-9_]+)", value):
                    if match.group(1) in globals():
                        value = value.replace(match.group(0), globals()[match.group(1)])
                    else:
                        value = value.replace(match.group(0), os.environ.get(match.group(1), match.group(0)))
                if subprocess.mswindows and "://" not in value:
                    value = value.replace("/", "\\")

            config[name] = value

    except (IOError, OSError):
        pass

    for option in ("MONITOR_INTERFACE", "CAPTURE_BUFFER", "LOG_DIR"):
        if not option in config:
            exit("[!] missing mandatory option '%s' in configuration file '%s'" % (option, config_file))

    for entry in (config.USERS or []):
        if len(entry.split(':')) != 4:
            exit("[!] invalid USERS entry '%s'" % entry)

    if config.CAPTURE_BUFFER:
        if config.CAPTURE_BUFFER.isdigit():
            BUFFER_LENGTH = int(config.CAPTURE_BUFFER)
        elif re.search(r"\d+%", config.CAPTURE_BUFFER):
            physmem = _get_total_physmem()

            if physmem:
                BUFFER_LENGTH = physmem * int(re.search(r"(\d+)%", config.CAPTURE_BUFFER).group(1)) / 100
            else:
                exit("[!] unable to determine total physical memory. Please use absolute value for 'CAPTURE_BUFFER'")

        BUFFER_LENGTH = BUFFER_LENGTH / BLOCK_LENGTH * BLOCK_LENGTH

def read_whitelist():
    WHITELIST.clear()

    _ = os.path.abspath(os.path.join(ROOT_DIR, "trails", "misc", "whitelist.txt"))
    if os.path.isfile(_):
        with open(_, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                else:
                    WHITELIST.add(line)

def read_ua():
    global SUSPICIOUS_UA_REGEX

    SUSPICIOUS_UA_REGEX = ""
    items = []

    _ = os.path.abspath(os.path.join(ROOT_DIR, "trails", "misc", "ua.txt"))
    if os.path.isfile(_):
        with open(_, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                else:
                    items.append(line)

    if items:
        SUSPICIOUS_UA_REGEX = "(?i)%s" % '|'.join(items)

if __name__ != "__main__":
    read_whitelist()
    read_ua()
