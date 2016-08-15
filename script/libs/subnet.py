#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
=========================================================
C段扫描模块
'''


import os
import sys
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT

from lxml import etree

from commons import Dict
from commons import YamlConf
from commons import URL



def nmapScan(cmd, scannerPath=None):
    '''
    Nmap scan.
    @returns:
        a list of host, each host has attribute 'ip' 'port'
    '''
    result = list()

    if "-oX" not in cmd:
        cmd = cmd + " -oX -"
    if scannerPath:
        cmd.replace("nmap", scannerPath)

    popen = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT)
    scanResult = popen.stdout.read()

    if not scanResult:
        return None
    #parse the nmap scan result
    xmlDoc = etree.XML(scanResult)
    hosts = xmlDoc.findall(".//host")
    for host in hosts:
        try:
            if host[0].get('state') != "up": continue
            ip = host[1].get('addr')

            ports = host.findall(".//port")
            for port in ports:
                if port[0].get('state') != "open": continue

                result.append(Dict(ip=ip, port=port.get('portid')))
        except IndexError:
            continue

    return result


def subnetScan(host, hostOnly=False, configFile=None):
    '''
    C段扫描
    '''
    if not URL.check(host):
        return None

    host = URL.getHost(host)

    confFile = configFile if configFile else os.path.join(sys.path[0],"script","data","port_mapping.yaml")

    conf = YamlConf(confFile)
    httpPorts = [str(k) for k in conf if conf[k]['protocol']=="http"]
    httpPorts = ",".join(httpPorts)

    if not hostOnly:
        nmapCmd = "nmap -n -PS{ports} -p{ports} {host}/24 -oX -".format(ports=httpPorts, host=host)
    else:
        nmapCmd = "nmap -n -PS{ports} -p{ports} {host} -oX -".format(ports=httpPorts, host=host)

    return nmapScan(nmapCmd)


