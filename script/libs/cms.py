#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
========================================================
CMS 识别
'''


import os
import sys

import thirdparty.requests as http

from commons import Log
from commons import PenError
from commons import YamlConf
from commons import URL



class CMSIdentify(object):
    '''
    CMS识别功能
    '''

    _fingerprintFile = os.path.join(sys.path[0],"script","data","cms_fingerprint.yaml")

    def __init__(self, baseURL, notFoundPattern=None):
        '''
        @params:
            baseURL: 待识别的站点的URL
            notFoundPattern: 指定notFoundPattern，有时候website只返回301或200，这时候需要该字段来识别‘404’
        '''
        baseURL = URL.getURI(baseURL)
        self.baseURL = baseURL.rstrip("/")
        self.notFoundPattern = notFoundPattern

        self.fp = YamlConf(self._fingerprintFile)

        self.log = Log("cmsidentify")


    def _checkPath(self, path, pattern):
        url = self.baseURL + path
        try:
            #response = http.get(url)
            response = http.get(url, allow_redirects=False)
        except http.ConnectionError as error:
            self.log.debug("Checking '{0}' failed, connection failed".format(url))
            return False

        if response.status_code == 200:
            if self.notFoundPattern:
                if self.notFoundPattern in response.content:
                    self.log.debug("Checking '{0}' failed, notFoundPattern matchs.".format(url))
                    return False
                #if response.history:
                #    if self.notFoundPattern in response.history[0].content:
                #        self.log.debug("Checking '{0}' failed, notFoundPattern matchs.".format(url))
                #        return False
            if not pattern:
                self.log.debug("Checking '{0}' success, status code 200.".format(url))
                return True
            else:
                if pattern in response.text:
                    self.log.debug("Checking '{0}' success, status code 200, match pattern {1}.".format(url,pattern))
                    return True
                else:
                    self.log.debug("Checking '{0}' failed, pattern not found.".format(url))
                    return False
        else:
            self.log.debug("Checking '{0}' failed, status code {1}".format(url, response.status_code))
            return False


    def _checkCMS(self, cmstype, cmsfp):
        matchList = []
        for line in cmsfp:
            if line['need']:
                if not self._checkPath(line['path'], line['pattern']):
                    return False
            else:
                if self._checkPath(line['path'], line['pattern']):
                    matchList.append([line['path'], line['pattern']])

        return matchList if matchList else False


    def identify(self):
        '''
        CMS识别
        @returns：
            (cmstype, matchs)：CMS识别结果，返回元组CMS类型，详细识别信息，如果识别失败，则matchs为空
        '''
        for cmstype,cmsfp in self.fp.iteritems():
            self.log.debug("Verify {0}".format(cmstype))
            matchs = self._checkCMS(cmstype, cmsfp)
            if matchs:
                break
        else:
            matchs = []

        return (cmstype,matchs)