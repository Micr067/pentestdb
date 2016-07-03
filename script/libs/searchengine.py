#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
================================================================
Search engine.
'''


import os
import sys
import random
import time

from lxml import etree

import thirdparty.yaml as yaml
import thirdparty.requests as http
from commons import Dict
from commons import YamlConf
from commons import PenError



class SearchEngineError(Exception):
    def __init__(self, reason=""):
        self.errMsg = "SearchEngineError. " + ("reason: "+reason if reason else "")

    def __str__(self):
        return self.errMsg



class UserAgents(object):
    def __new__(cls):
        configFile = os.path.join(sys.path[0],"script","data","user-agents.yaml")
        try:
            config = YamlConf(configFile)
        except PenError:
            userAgents = ["Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)",
                "Mozilla/5.0 (Windows; U; Windows NT 5.2)Gecko/2008070208 Firefox/3.0.1",
                "Opera/9.27 (Windows NT 5.2; U; zh-cn)",
                "Mozilla/5.0 (Macintosh; PPC Mac OS X; U; en)Opera 8.0)"]
        else:
            userAgents = [x['User-Agent'] for x in config]

        return userAgents



class SearchConfig(object):
    def __new__(cls, engine):
        configFile = os.path.join(sys.path[0],"script","data","search_engine.yaml")
        try:
            with open(configFile, "r") as _file:
                config = yaml.load(_file)[engine]
        except IOError:
            raise SearchEngineError("read searchengine configuration file 'searchengine.yaml' failed")
        else:
            return config



class Query(object):
    '''
    Build query keyword
    @examples:
        query = Query(site="xxx.com") | -Query(site="www.xxx.com") | Query(kw="password")
        query.doSearch(engine="baidu")
    '''

    allowEngines = ['baidu', 'bing', 'google']

    def __init__(self, **kwargs):
        '''
        @params:
            site: seach specified site
            title: search in title
            url: search in url
            filetype: search files with specified file type
            link: search in link
            kw: raw keywords to search 
        '''
        # _qlist record the query value, format [-/+, key, value]
        self._qlist = list()
        self.queryResult = list()

        keylist = ['site','title','url','filetype','link','kw']
        for key,value in kwargs.iteritems():
            if key not in keylist:
                self._qlist.append(["",'kw',value])
            self._qlist.append(["",key,value])


    def __neg__(self):
        self._qlist[0][0] = "-"
        return self

    def __pos__(self):
        self._qlist[0][0] = "+"
        return self

    def __or__(self, obj):
        self._qlist += obj._qlist
        return self


    def genKeyword(self, engine):
        '''
        Generate keyword string.
        '''
        config = SearchConfig(engine)
        keyword = ""
        for line in self._qlist:
            if line[1] in config['ghsyn']:
                if config['ghsyn'][line[1]]:
                    keyword += line[0] + config['ghsyn'][line[1]] + ":" + line[2] + " "
                else:
                    keyword += line[0] + line[2] + " "
            elif line[1] == "kw":
                keyword += line[0] + line[2] + " "

        return keyword.strip()


    def doSearch(self, engine="baidu", size=20):
        '''
        Search in search engine.
        '''
        keyword = self.genKeyword(engine)
        if engine == "baidu":
            baidu = Baidu(size=size)
            return baidu.search(keyword)
        elif engine == "bing":
            bing = Bing(size=size)
            return bing.search(keyword)
        elif engine == "google":
            google = Google(size=size)
            return google.search(keyword)
        else:
            raise SearchEngineError("engine {0} is not support".format(engine))



class SearchEngine(object):
    '''
    Base searchengine class.
    @params:
        size: specified the amount of the result
        engine: the engine name
    '''
    def __init__(self, engine, size=20):
        self.size = size
        self.retry = 20
        self.config = SearchConfig(engine)
        self.userAgents = UserAgents()

        self.url = self.config['url']
        self.defaultParam = dict(**self.config['default'])

        #this signature string illustrate the searchengine find something, should be redefined in subclass
        self.findSignature = ""
        #this signature string illustrate the searchengine find nothing, should be redefined in subclass
        self.notFindSignature = ""


    def search(self, keyword, size=None):
        '''
        Use searchengine to search specified keyword.
        @params:
            keyword: the keyword to search
            size: the length of search result
        '''
        size = size if size else self.size
        pageSize = self.config['param']['pgsize']['max']
        pages = size / pageSize

        params = self.defaultParam
        params.update({self.config['param']['query']: keyword})
        params.update({self.config['param']['pgsize']['key']: pageSize})

        result = list()
        for p in xrange(pages+1):
            params.update({self.config['param']['pgnum']: p*pageSize})

            for item in self._search(params):
                yield item


    def _search(self, params):
        '''
        Request with specified param, parse the response html document.
        @params:
            params: the query params
        @returns:
            return the search result, result format is:
                [[titel,url,brief-information],[...]...]
        '''
        for i in xrange(self.retry):
            #use delay time and random user-agent to bypass IP restrict policy
            delayTime = random.randint(1,3)
            time.sleep(delayTime)

            userAgent = self.userAgents[random.randint(0,len(self.userAgents))-1]
            xforward = "192.168.3." + str(random.randint(1,255))

            headers = {"User-Agent":userAgent, "X-Forward-For":xforward, "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3"}
            try:
                response = http.get(self.url, headers=headers, params=params)
            except http.RequestException as error:
                continue
            
            # 如果findSignature没有找到，则可能说明触发了搜索引擎的IP限制策略，此时retry；如果找到则无需retry
            if self.findSignature in response.text:
                for item in self._parseHtml(response.text):
                    yield item
                break
            elif self.notFindSignature in response.text:
                raise StopIteration()
        else:
            raise StopIteration()


    def _parseHtml(self, document):
        '''
        Parse html return the formated result. Should be redefine in subclass.
        @params:
            the html document
        @returns:
            return the formated search result, result format is:
                [[titel,url,brief-information],[...]...]
        '''
        return list()



class Baidu(SearchEngine):
    '''
    Baidu search engine.
    @params:
        size: specified the amount of the result
    @examples:
        baidu=Baidu()
        baidu.search("site:xxx.com password.txt")
    '''
    def __init__(self, size=200):
        super(Baidu,self).__init__("baidu",size)
        self.findSignature = "class=f"
        self.notFindSignature = "noresult.html"

    def _parseHtml(self, document):
        tree = etree.HTML(document)
        for node in tree.xpath("//td[@class='f']/a"):
            title = "".join([x for x in node.itertext()])
            url = node.get("href")
            yield Dict(title=title, url=url)



class Bing(SearchEngine):
    '''
    Bing search engine.
    @params:
        size: specified the amount of the result
    @examples:
        bing=Bing()
        bing.search("site:xxx.com password.txt")
    '''
    def __init__(self, size=200):
        super(Bing,self).__init__("bing",size)
        self.findSignature = 'class="b_algo"'
        self.notFindSignature = 'class="b_no"'

    def _parseHtml(self, document):
        tree = etree.HTML(document)
        for node in tree.xpath("//li[@class='b_algo']/h2/a"):
            title = "".join([x for x in node.itertext()])
            url = node.get("href")
            yield Dict(title=title, url=url)



class Google(SearchEngine):
    '''
    Google search engine.
    @params:
        size: specified the amount of the result
    @examples:
        google=Google()
        google.search("site:xxx.com password.txt")
    '''
    def __init__(self, size=200):
        super(Google,self).__init__("google",size)
        self.findSignature = 'class="r"'

    def _parseHtml(self, document):
        tree = etree.HTML(document)
        for node in tree.xpath("//h3[@class='r']/a"):
            title = "".join([x for x in node.itertext()])
            url = node.get("href")
            urlStart = url.find("http")
            urlEnd = url.find("&sa")
            urlStart = urlStart if urlStart!=-1 else 0
            urlEnd = urlEnd if urlEnd!=-1 else len(url)
            yield Dict(title=title, url=url[urlStart:urlEnd])



