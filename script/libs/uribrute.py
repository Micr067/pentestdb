#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
==================================================================================
URI 爆破.
爆破网站备份，配置文件备份, 后台路径以及其他敏感文件.
'''


import os
import sys
import random
import time
import urlparse

import thirdparty.requests as http

from commons import Log
from commons import PenError
from commons import YamlConf
from commons import URL



class URIBruter(object):
    '''
    URI bruteforce.
    @remarks:
        allowTypes: 字典类型列表，["webbak","cfgbak","interestfile","webconsole"]
    '''
    allowTypes = ["webbak","cfgbak","interestfile","webconsole"]

    _dirInfoFile = os.path.join(sys.path[0],"script","data","uri_brute.yaml")
    _javaConsoleFile = os.path.join(sys.path[0],"script","data","java_webconsole.yaml")

    def __init__(self, types, keywords=[], exts=[], size="small", url=None):
        '''
        @params:
            keywords: 指定关键字列表，关键字用于生成备份文件字典
            exts: 指定文件后缀列表，生成的字典文件会自动加入这些后缀
        '''
        self.types = types

        self.keywords = keywords
        self.exts = exts if exts else ["php"]
        self.size = size

        self.dirInfo = self._loadDirInfo()
        self.log = Log("uribrute")


    def _getKeywordFromURL(self, url):
        '''
        从URL中提取关键字，例如xxx.com 提取 xxx，该关键字将用于生成web备份文件字典
        '''
        host = urlparse.urlparse(url)[1]
        if not host:
            return None

        if URL.isIP(url):
            return None

        hostsp = host.split(".")
        try:
            if host.startswith("www."):
                keyword = hostsp[1]
            else:
                keyword = hostsp[0]
        except IndexError:
            return None

        return keyword


    def _genKeywordWebbakDict(self):
        '''
        根据用户指定关键字生成web_backup字典
        '''
        suffixList = self.dirInfo['web_bak_file']

        result = []
        for suffix in suffixList:
            for keyword in self.keywords:
                result.append("".join([keyword,suffix]))
                result.append("-".join([keyword,suffix]))
                result.append("_".join([keyword,suffix]))

        return [unicode(x) for x in self.keywords] + result


    def _loadJavaConsoleDict(self):
        result = []
        javaConsoleInfo = YamlConf(self._javaConsoleFile)
        for server, consoles in javaConsoleInfo.iteritems():
            for console in consoles:
                if console['type'] == "http":
                    if console['url'] != "/":
                        result.append(console['url'])

        return result


    def _loadDirInfo(self):
        '''
        加载url_brute.yaml数据文件，处理'<ext>'占位符，返回dirInfo字典
        '''
        result = {}
        dirInfo = YamlConf(self._dirInfoFile)

        for key, value in dirInfo.iteritems():
            result[key] = []
            for line in value:
                if "<ext>" in line:
                    for ext in self.exts:
                        result[key].append(line.replace("<ext>", ext))
                else:
                    result[key].append(line)

        return result


    def _dictIter(self):
        '''
        返回特定类型字典的生成器
        '''
        if "webbak" in self.types:
            if self.keywords:
                self.dirInfo['web_bak_file'] += self._genKeywordWebbakDict()
            if self.size == "small":
                self.dirInfo['web_bak_dir'] = []
            for zdir in [""]+self.dirInfo['web_bak_dir']:
                for zfile in self.dirInfo['web_bak_file']:
                    for ext in self.dirInfo['web_bak_ext']:
                        if zdir:
                            yield "/"+zdir+"/"+zfile+ext
                        else:
                            yield "/"+zfile+ext

        if "cfgbak" in self.types:
            if self.size == "small":
                self.dirInfo['cfg_bak_dir'] = []
            for bdir in [""]+self.dirInfo['cfg_bak_dir']:
                for bfile in self.dirInfo['cfg_bak_file']:
                    for ext in self.dirInfo['cfg_bak_ext']:
                        if bdir:
                            yield "/"+bdir+"/"+bfile+ext
                        else:
                            yield "/"+bfile+ext

        if "webconsole" in self.types:
            for cdir in [""]+self.dirInfo['web_console_dir']:
                for cfile in self.dirInfo['web_console_file']:
                    if cdir:
                        yield "/"+cdir+cfile
                    else:
                        yield "/"+cfile

        if "interestfile" in self.types:
            for line in self.dirInfo['interest_file']:
                yield "/"+line

        if "jsp" in self.exts:
            for line in self._loadJavaConsoleDict():
                yield line


    def genDict(self, url=None):
        '''
        生成特定类型的字典文件
        '''
        if url:
            keyword = self._getKeywordFromURL(url)
            if keyword:
                self.keywords.append(keyword)

        result = []
        for line in self._dictIter():
            result.append(line)

        return result


    def _safeRequest(self, safeURL):
        '''
        安全请求，用于绕过WAF等安全设备
        '''
        if not safeURL:
            return
        #url = random.choice(safeURL.split())
        try:
            http.get(safeURL)
        except http.ConnectionError:
            pass


    def bruteforce(self, baseURL, notFoundPattern=None, safeURL=None, timeout=10, delay=0):
        '''
        爆破
        '''
        baseURL = URL.getURI(baseURL)

        keyword = self._getKeywordFromURL(baseURL)
        if keyword:
            self.keywords.append(keyword)

        matchs = []
        baseURL = baseURL.rstrip("/")
        for line in self._dictIter():
            time.sleep(delay)
            self._safeRequest(safeURL)

            url = baseURL.rstrip("/") + line
            try:
                self.log.debug(u"request url '{0}'".format(url))
                #response = http.get(url, timeout=timeout)
                response = http.get(url, timeout=timeout, allow_redirects=False)
            except http.ConnectionError:
                continue
            if response.status_code == 200:
                if notFoundPattern:
                    if notFoundPattern in response.content:
                        continue
                    #if response.history:
                    #    if notFoundPattern in response.history[0].content:
                    #        continue
                else:
                    self.log.debug(u"find available url '{0}'".format(url))
                    matchs.append(url)
            else:
                continue

        return matchs
