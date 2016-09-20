#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
'''


import os
import sys
import logging
import types
import re
import urlparse
import urllib

from lxml import etree
import thirdparty.yaml as yaml



class PenError(Exception):
    def __init__(self, errorMsg):
        self.errorMsg = errorMsg

    def __str__(self):
        #return self.errorMsg.encode(sys.stdout.encoding)
        return self.errorMsg



class DictError(PenError):
    def __str__(self):
        return str(" ".join(["Dict error", self.errorMsg]))



def exceptionHook(etype, evalue, trackback):
    if isinstance(evalue, KeyboardInterrupt):
        print "User force exit."
        exit()
    else:
        sys.__excepthook__(etype, evalue, trackback)



def addSlashes(line):
    d = {'"':'\\"', "'":"\\'", "\0":"\\\0", "\\":"\\\\"}
    return "".join([d.get(x,x) for x in line])


def stripSlashes(line):
    r = line.replace('\\"', '"')
    r = r.replace("\\'", "'")
    r = r.replace("\\\0", "\0")
    r = r.replace("\\\\", "\\")
    return r



class WordList(object):
    '''
    字典文件迭代器
    '''
    def __init__(self, fileName, lineParser=None):
        self._fileName = fileName
        self._lineParser = lineParser
        try:
            self._file = open(self._fileName, 'r')
        except IOError:
            raise PenError("Loading wordlist file '{0}' failed".format(fileName))


    def _defaultLineParser(self, line):
        line = line.strip()
        if line.startswith("/**"):
            return None

        if self._lineParser:
            line = self._lineParser(line)

        return line if line else None



    def __iter__(self):
        return self


    def next(self):
        line = self._file.readline()
        if line == '':
            self._file.close()
            raise StopIteration()
        else:
            line = self._defaultLineParser(line)

            return line if line else self.next()



class Dict(dict):
    def __init__(self, **kwargs):
        super(Dict, self).__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("object dose not have attribute '{0}'".format(key))

    def __setattr__(self, key, value):
        self[key] = value



class YamlConf(object):
    '''
    Yaml配置文件加载器
    '''
    def __new__(cls, path):
        try:
            _file = open(path,"r")
            result = yaml.load(_file)
        except IOError:
            raise PenError("Loading yaml file '{0}' failed, read file failed".format(path))
        except yaml.YAMLError as error:
            raise PenError("Loading yaml file '{0}' failed, yaml error, reason: '{1}'".format(path,str(error)))
        except Exception as error:
            raise PenError("Loading yaml file '{0}' failed, reason: {1}".format(path,str(error)))

        return result



class Output(object):
    '''
    终端输出功能
        该类用于输出信息到控制台和文件
    '''
    _RED = '\033[31m'
    _BLUE = '\033[34m'
    _YELLOW = '\033[33m'
    _GREEN = '\033[32m'
    _EOF = '\033[0m'

    _WIDTH = 80
    _CHAR = "-"

    def __init__(self, title=None, tofile=None):
        '''
        @params:
            title: 输出的标题
            tofile: 输出文件
        '''
        self._title = title
        self._fileName = tofile
        self._file = self._openFile(tofile)


    def _openFile(self, filename):
        if filename:
            try:
                _file = open(filename, "w")
            except IOError:
                _file = None
                raise PenError("open output file '{0}' failed".format(filename))
        else:
            _file = None

        return _file


    def openFile(self, filename):
        self._fileName = filename
        self._file = self._openFile(filename)


    def init(self, title=None, tofile=None):
        if title: self._title = title
        if tofile: 
            self._fileName = tofile
            self._file = self._openFile(tofile)
        
        self.raw(self._banner())
        self.yellow(u"[{0}]".format(self._title))
        self.raw(self._CHAR * self._WIDTH)


    @classmethod
    def safeEncode(cls, msg, method=None):
        '''
        安全编码
            如果msg中有不能编码的字节，自动处理为16进制
        '''
        if isinstance(msg, str):
            return msg
        elif isinstance(msg, unicode):
            method = method.lower() if method else sys.stdin.encoding
            try:
                return msg.encode(method)
            except UnicodeError:
                resultList = []
                for word in msg:
                    try:
                        encodedWord = word.encode(method)
                    except UnicodeError:
                        encodedWord = "\\x" + repr(word)[4:6] + "\\x" + repr(word)[6:8]

                    resultList.append(encodedWord)

                return "".join(resultList)
        else:
            try:
                msg = unicode(msg)
            except UnicodeDecodeError:
                msg = str(msg)
            return cls.safeEncode(msg,method)



    @classmethod
    def R(cls, msg):
        '''
        字符串着色为红色
        '''
        return cls._RED + msg + cls._EOF

    @classmethod
    def Y(cls, msg):
        '''
        字符串着色为橙色
        '''
        return cls._YELLOW + msg + cls._EOF

    @classmethod
    def B(cls, msg):
        '''
        字符串着色为蓝色
        '''
        return cls._BLUE + msg + cls._EOF

    @classmethod
    def G(cls, msg):
        '''
        字符串着色为绿色
        '''
        return cls._GREEN + msg + cls._EOF


    @classmethod
    def raw(cls, msg):
        '''
        无颜色输出
        '''
        print cls.safeEncode(msg)
    

    @classmethod
    def red(cls, msg):
        '''
        打印红色信息
        '''
        cls.raw(cls.R(msg))

    @classmethod
    def yellow(cls, msg):
        '''
        打印橙色信息
        '''
        cls.raw(cls.Y(msg))

    @classmethod
    def blue(cls, msg):
        '''
        打印蓝色信息
        '''
        cls.raw(cls.B(msg))

    @classmethod
    def green(cls, msg):
        '''
        打印绿色信息
        '''
        cls.raw(cls.G(msg))


    @classmethod
    def info(cls, msg):
        cls.raw(msg)

    @classmethod
    def error(cls, msg):
        cls.red(msg)

    @classmethod
    def warnning(cls, msg):
        cls.yellow(msg)


    def write(self, data):
        '''
        写入数据到文件
        '''
        if self._file:
            try:
                self._file.write(data)
                return True
            except IOError:
                raise PenError("write output file '{0}' failed".format(self._fileName))
        else:
            return False


    def writeLine(self, line, parser=None):
        '''
        写入一行数据到文件
        @params:
            line: 待写入的数据
            parser: 处理待写入数据的回调函数
        '''
        if self._file:
            if parser and isinstance(parser, types.FunctionType):
                line = parser(line)
            try:
                self._file.write(line + "\n")
                return True
            except IOError:
                raise PenError("write output file '{0}' failed".format(self._fileName))
        else:
            return False


    def _banner(self):
        '''
        生成banner信息
        '''
        fmt = "|{0:^" + "{0}".format(self._WIDTH+7) + "}|"

        banner = "+" + self._CHAR * (self._WIDTH-2) + "+\n"
        banner = banner + fmt.format(self.Y("PentestDB.") + " Tools and Resources for Web Penetration Test.") + "\n"
        banner = banner + fmt.format(self.G("https://github.com/alpha1e0/pentestdb")) + "\n"
        banner = banner + "+" + self._CHAR * (self._WIDTH-2) + "+\n"

        return banner


    def close(self):
        self.raw(self._CHAR * self._WIDTH)
        if self._file:
            self._file.close()


    def __enter__(self):
        self.init()
        return self


    def __exit__(self, *args):
        self.close()
        


class Log(object):
    '''
    Log class
        support:critical, error, warning, info, debug, notset
    Params:
        logname: specify the logname
        toConsole: whether outputing to console
        tofile: whether to logging to file
    '''
    def __new__(cls, logname=None, toConsole=True, tofile="pen"):
        logname = logname if logname else "pen"

        log = logging.getLogger(logname)
        log.setLevel(logging.DEBUG)

        if toConsole:
            streamHD = logging.StreamHandler()
            streamHD.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] <%(levelname)s> %(message)s' ,datefmt="%Y-%m-%d %H:%M:%S")
            streamHD.setFormatter(formatter)
            log.addHandler(streamHD)

        if tofile:
            fileName = os.path.join(sys.path[0],"script","log",'{0}.log'.format(tofile))
            try:
                if not os.path.exists(fileName):
                    with open(fileName,"w") as fd:
                        fd.write("{0} log start----------------\r\n".format(tofile))
            except IOError:
                raise PenError("Creating log file '{0}' failed".format(fileName))
            fileHD = logging.FileHandler(fileName)
            fileHD.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] <%(levelname)s> %(message)s' ,datefmt="%Y-%m-%d %H:%M:%S")
            fileHD.setFormatter(formatter)
            log.addHandler(fileHD)

        return log



class URL(object):
    '''
    URL处理
    '''
    _urlPattern = re.compile(r"^((?:http(?:s)?\://)?(?:[-0-9a-zA-Z_]+\.)+(?:[-0-9a-zA-Z_]+)(?:\:\d+)?)[^:]*$")
    _ipPattern = re.compile(r"^(?:http(s)?\://)?(\d+\.){3}(\d+)(?:\:\d+)?.*")

    @classmethod
    def check(cls, url):
        '''
        检查URL格式是否正确
        '''
        matchs = cls._urlPattern.match(url)
        if not matchs:
            return False
        else:
            return True


    @classmethod
    def isIP(cls, url):
        '''
        检查URL是否是ip类型的url
        '''
        matchs = cls._ipPattern.match(url)
        if matchs:
            return True
        else:
            return False


    @classmethod
    def _completeURL(cls, url):
        '''
        补全URL
            如果URL不包含协议类型，则补全协议类型
        '''
        if "://" not in url:
            url = "http://" + url

        if not cls.check(url):
            raise PenError("url format error")

        return url


    @classmethod
    def format(cls, url):
        '''
        格式化url
        @returns:
            protocol/url/host/path/baseURL/params: baseURL类似于dirname
        @examples:
            http://www.aaa.com/path/index.php?a=1&b=2
            protocol: http
            uri: http://www.aaa.com/path/index.php
            host: www.aaa.com
            path: /path/index.php
            baseURL: http://www.aaa.com/path/ baseURL依据URL末尾是否有"/"来判断，返回结果以"/"结束
            params: {'a': '1', 'b': '2'}
        '''
        url = cls._completeURL(url)
        parsed = urlparse.urlparse(url)

        protocol = parsed[0]
        host = parsed[1]
        uri = parsed[0] + "://" + parsed[1] + parsed[2]
        path = parsed[2]

        if not path.endswith("/"):
            sp = path.split("/")
            baseURL = parsed[0] + "://" + parsed[1] + "/".join(sp[0:-1]) + "/"
        else:
            baseURL = uri

        params = dict()

        for param in parsed[4].split("&"):
            if not param:
                continue
            sp = param.split("=")
            try:
                params[sp[0]] = urllib.unquote(sp[1])
            except IndexError:
                params[sp[0]] = ""

        return Dict(protocol=protocol,uri=uri,host=host,path=path,baseURL=baseURL,params=params)


    @classmethod
    def getHost(cls, url):
        url = cls._completeURL(url)
        parsed = urlparse.urlparse(url)

        return parsed[1]


    @classmethod
    def getURI(cls, url):
        url = cls._completeURL(url)
        parsed = urlparse.urlparse(url)

        return parsed[0] + "://" + parsed[1] + parsed[2]


