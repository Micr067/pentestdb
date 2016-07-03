#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
'''


import os
import sys

from commons import PenError
from commons import WordList
from commons import Dict
from thirdparty.dns import resolver, reversename, query
from thirdparty.dns.exception import DNSException



class DnsResolver(object):
    '''
    DNS 解析器
    '''
    def __init__(self, domain=None, timeout=None):
        self.domain = domain

        self._resolver = resolver.Resolver()
        # DNS server configure
        self._resolver.nameservers = ['223.5.5.5','8.8.4.4']
        # DNS query timeout configure
        self._resolver.timeout = 10

        self._axfr = query.xfr


    def domain2IP(self, domain=None):
        '''
        Parse domain to IP.
        '''
        domainToResolve = domain if domain else self.domain
        try:
            response = self._resolver.query(domainToResolve, "A")
        except DNSException:
            return None
        else:

            return response[0].to_text()


    def IP2domain(self, ip):
        '''
        Parse IP to domain. The most dns server dose not support this operation.
        '''
        return reversename.from_address(ip)


    def getRecords(self, rtype, domain=None):
        '''
        Get DNS records
        @returns
            [domain, value, type]: records type supports "A", "CNAME", "NS", "MX", "SOA", "TXT"
        @examples
            dns.getRecords("A")
        '''
        if not rtype in ["A", "CNAME", "NS", "MX", "SOA", "TXT", "a", "cname", "ns", "mx", "soa", "txt"]:
            return []

        domainToResolve = domain if domain else self.domain
        try:
            response = self._resolver.query(domainToResolve, rtype)
        except DNSException:
            return []

        if not response:
            return []

        if rtype in ["MX","mx"]:
            return [[domainToResolve, line.to_text().rstrip(".").split()[-1], rtype] for line in response]
        return [[domainToResolve, line.to_text().rstrip("."), rtype] for line in response]


    def getZoneRecords(self, domain=None):
        '''
        Get DNS zone records
            Check and use dns zone transfer vulnerability. This function will traverse all the 'ns' server
        @examples:
            dnsresolver = DnsResolver('aaa.com')
            records = dnsresolver.getZoneRecords()
        '''
        domainToResolve = domain if domain else self.domain

        records = list()
        nsRecords = self.getRecords("NS", domainToResolve)
        for serverRecord in nsRecords:
            xfrHandler = self._axfr(serverRecord[1], domainToResolve)
            try:
                for response in xfrHandler:
                    topDomain = response.origin.to_text().rstrip(".")
                    for line in response.answer:
                        # A records
                        if line.rdtype == 1:
                            lineSplited = line.to_text().split()
                            if lineSplited[0] != "@":
                                subDomain = lineSplited[0] + "." + topDomain
                                ip = lineSplited[-1]
                                records.append([subDomain, ip, "A"])
                        # CNAME records
                        elif line.rdtype == 5:
                            lineSplited = line.to_text().split()
                            if lineSplited[0] != "@":
                                subDomain = lineSplited[0] + "." + topDomain
                                aliasName = lineSplited[-1]
                                records.append([subDomain, aliasName, "CNAME"])
            except:
                pass

        return records


    def getZoneRecords2(self, server, domain=None):
        '''
        Get DNS zone records
            Use the specified ns server, check and use dns zone transfer vulnerability.
        @examples:
            dnsresolver = DnsResolver('aaa.com')
            records = dnsresolver.getZoneRecords2()
        '''
        domainToResolve = domain if domain else self.domain

        records = list()

        xfrHandler = self._axfr(server, domainToResolve)

        try:
            for response in xfrHandler:
                topDomain = response.origin.to_text().rstrip(".")
                for line in response.answer:
                    # A records
                    if line.rdtype == 1:
                        lineSplited = line.to_text().split()
                        if lineSplited[0] != "@":
                            subDomain = lineSplited[0] + "." + topDomain
                            ip = lineSplited[-1]
                            records.append([subDomain, ip, "A"])
                    # CNAME records
                    elif line.rdtype == 5:
                        lineSplited = line.to_text().split()
                        subDomain = lineSplited[0] + "." + topDomain
                        if lineSplited[0] != "@":
                            aliasName = lineSplited[-1]
                            records.append([subDomain, aliasName, "CNAME"])
        except:
            pass

        return records


    def resolveAll(self, domain=None):
        domainToResolve = domain if domain else self.domain
        types = ["A", "CNAME", "NS", "MX", "SOA", "TXT"]
        records = list()

        for t in types:
            records += self.getRecords(t, domainToResolve)

        records += self.getZoneRecords(domainToResolve)

        return records



class DnsBruter(object):
    '''
    Use wordlist to bruteforce subdomain.
    @params:
        domain: the domain to bruteforce
        dictfiles: the dict files
        bruteTopDomain: wither to check top domain
    '''

    _defaultSubDomainDict = os.path.join(sys.path[0],"dns","subdomain_small.txt")
    _defaultTopDomainDict = os.path.join(sys.path[0],"dns","toplevel.txt")

    def __init__(self, domain, dictfile=None, bruteTopDomain=False):
        '''
        @params:
            domain: the domain to bruteforce
            dictfiles: the dict files
            bruteTopDomain: wither to check top domain
        '''
        self._domain = domain.strip(".")
        #partDomain用于顶级域名爆破，示例：aaa.com partDomain为aaa，aaa.com.cn partDomain为aaa
        pos = self._domain.rfind(".com.cn")
        if pos==-1: pos = self._domain.rfind(".")
        self._partDomain = self._domain if pos==-1 else self._domain[0:pos]

        self._dictfile = dictfile if dictfile else self._defaultSubDomainDict

        self._bruteTopDomain = bruteTopDomain
        self._dnsresolver = DnsResolver()


    def _checkDomain(self, domain):
        '''
        check the domain, if available return ip else return None
        '''
        ip = self._dnsresolver.domain2IP(domain)
        if ip:
            return ip
        else:
            return None


    def __iter__(self):
        return self.brute()


    def brute(self):
        if self._bruteTopDomain:
            for line in WordList(self._defaultTopDomainDict):
                domain = partDomain + "." + line
                ip = self._checkDomain(domain)
                if ip:
                    yield Dict(domain=domain, ip=ip)

        for line in WordList(self._dictfile):
            domain = line.strip() + "." + self._domain
            ip = self._checkDomain(domain)
            if ip:
                yield Dict(domain=domain, ip=ip)


