#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
'''


import sys
import argparse
import os
import glob
import re
import importlib
import inspect

from script.libs.commons import PenError
from script.libs.commons import WordList
from script.libs.commons import Log
from script.libs.commons import Output
from script.libs.commons import URL
from script.libs.cms import CMSIdentify
from script.libs.password import PasswdGenerator
from script.libs.uribrute import URIBruter
from script.libs.coder import Code
from script.libs.coder import EncodeError
from script.libs.coder import DecodeError
from script.libs.coder import File
from script.libs.coder import FileError
from script.libs.exploit import Exploit
from script.libs.exploit import ExpModel
from script.libs.exploit import ExploitError
from script.libs.exploit import NotImplementError
from script.libs.orm import ORMError
from script.libs.orm import DBError
from script.libs.searchengine import Query
from script.libs.searchengine import Baidu
from script.libs.searchengine import Bing
from script.libs.searchengine import Google
from script.libs.searchengine import SearchEngineError
from script.libs.dnsparse import DnsResolver
from script.libs.dnsparse import DnsBruter
from script.libs.subnet import subnetScan
from script.libs.service import Service



def handleException(func):
    '''
    异常处理
        函数修饰器，用于集中异常处理
    '''
    def _wrapper(args):
        try:
            out = Output()
            return func(args, out)
        except PenError as error:
            out.error(str(error))
        except ExploitError as error:
            out.error(str(error))
        except NotImplementError as error:
            out.error(str(error))
        except ORMError as error:
            out.error(str(error))
        except SearchEngineError as error:
            out.error(str(error))
        except DecodeError as error:
            out.error(str(error))
        except FileError as error:
            out.error(str(error))
        #except Exception as error:
        #    out.error(u"未知错误, '{0}'".format(error))
        except KeyboardInterrupt:
            out.error(u"强制退出")
        finally:
            out.close()

    return _wrapper



class atParamParser(argparse.Action):
    '''
    处理@file类型参数处理器
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        if values.startswith("@"):
            newValues = WordList(values[1:])
        else:
            newValues = [values]

        setattr(namespace, self.dest, newValues)


class fileopFileParamParser(argparse.Action):
    '''
    fileop模块file类型参数处理器
    @remarks:
        filePath@fileType参数 处理为 (filePath, fileType)
        filePath 处理为 (filePath, None)
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        if "@" in values:
            splited = values.split("@")
            setattr(namespace, self.dest, (splited[0].strip(), splited[1].strip().lower()))
        else:
            setattr(namespace, self.dest, (values,None))


class exploitQueryParamParser(argparse.Action):
    '''
    exploit模块--query参数处理器
    @remarks:
        column:keyword参数会处理为(column, keyword)元组，表示列和关键字
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        columns = ['expName', 'os', 'webserver', 'language', 'appName']
    
        if ":" not in values:
            column = 'expName'
            keyword = values.strip().decode(sys.stdout.encoding)
        else:
            splited = values.split(":")
            column = splited[0].strip()
            keyword = ":".join(splited[1:]).decode(sys.stdout.encoding)

        if column not in columns:
            raise ExploitError("search param error, should be one of '{0}'".format(columns))

        setattr(namespace, self.dest, (column,keyword))


class exploitExecuteParamParser(argparse.Action):
    '''
    exploit模块--execute参数处理器
    @remarks:
        column:keyword参数会处理为exploit文件名数组，其中每项元素为exploit文件名
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        columns = ['expName', 'os', 'webserver', 'language', 'appName']

        if values.endswith(".py"):
            expFileList = [values]
        else:
            if ":" not in values:
                column = 'expName'
                keyword = values.strip().decode(sys.stdout.encoding)
            else:
                splited = values.split(":")
                column = splited[0].strip()
                keyword = ":".join(splited[1:]).decode(sys.stdout.encoding) 

            if column not in columns:
                raise ExploitError("search param error, should be one of '{0}'".format(columns))

            exploits = ExpModel.search(column, keyword)
            if exploits:
                expFileList = [e.expFile for e in exploits]
            else:
                expFileList = []

        setattr(namespace, self.dest, expFileList)


class exploitUseragentParamParser(argparse.Action):
    '''
    exploit模块--useragent参数处理器
    @remarks:
        useragent会自动加入args.allHeaders
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, 'allHeaders'):
            namespace.allHeaders = {'User-Agent': values}
        else:
            namespace.allHeaders['User-Agent'] = values

        setattr(namespace, self.dest, values)


class exploitRefererParamParser(argparse.Action):
    '''
    exploit模块--referer参数处理器
    @remarks:
        referer会自动加入args.allHeaders
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, 'allHeaders'):
            namespace.allHeaders = {'Referer': values}
        else:
            namespace.allHeaders['Referer'] = values

        setattr(namespace, self.dest, values)


class exploitHeadersParamParser(argparse.Action):
    '''
    exploit模块--headers参数处理器
    @remarks:
        自定义的headers会自动加入args.allHeaders
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        newValues = {}
        if not hasattr(namespace, 'allHeaders'):
            namespace.allHeaders = {}

        for paramPair in values.split("#"):
            paramPairSplited = paramPair.strip().split("=")
            if len(paramPairSplited) > 1:
                namespace.allHeaders[paramPairSplited[0]] = "=".join(paramPairSplited[1:])
                newValues[paramPairSplited[0]] = "=".join(paramPairSplited[1:])
            else:
                namespace.allHeaders[paramPairSplited[0]] = ""
                newValues[paramPairSplited[0]] = ""

        setattr(namespace, self.dest, newValues)


class exploitCookieParamParser(argparse.Action):
    '''
    exploit模块--cookie参数处理器
    @remarks:
        http:http://127.0.0.1:8080 会被转换为字典类型 {'http' : 'http://127.0.0.1:8080'}
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        strCookie = values.strip()
        if strCookie.find("Cookie:") == 0:
            strCookie = strCookie[7:].lstrip()  

        newValues = {}
        for cookiePair in strCookie.split(";"):
            cookiePair = cookiePair.strip()
            if not cookiePair:
                continue
            try:
                name,value = cookiePair.split("=")
            except ValueError:
                name,value = cookiePair,""
            except Exception as ex:
                raise ExploitError(str(ex))
            name,value = name.strip(), value.strip()
            if not name: continue
            newValues[name] = value

        setattr(namespace, self.dest, newValues)


class exploitProxyParamParser(argparse.Action):
    '''
    exploit模块--proxy参数处理器
    @remarks:
        http:http://127.0.0.1:8080 会被转换为字典类型 {'http' : 'http://127.0.0.1:8080'}
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        newValues = {}

        pattern = re.compile(r"(http|https):((?:\w+)://.+)")
        matchs = pattern.match(values)
        if not matchs:
            raise ExploitError("exploit --proxy parameter format error")

        newValues[matchs.groups()[0]] = matchs.groups()[1]

        setattr(namespace, self.dest, newValues)


class exploitElseargsParamParser(argparse.Action):
    '''
    exploit模块--elseargs参数处理器
    @remarks:
        xxx=xxxx#yyy=yyyy 会被转换为字典类型 {xxx:xxxx, yyy:yyyy}
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        newValues = {}

        for paramPair in values.split("#"):
            paramPairSplited = paramPair.strip().split("=")
            if len(paramPairSplited) > 1:
                newValues[paramPairSplited[0]] = "=".join(paramPairSplited[1:])
            else:
                newValues[paramPairSplited[0]] = ""

        setattr(namespace, self.dest, newValues)



def _loadExpClass(expFile):
    '''
    Exploit类加载
    @params：
        expFile: Exploit文件路径
    '''
    expFile = os.path.join(sys.path[0], "exploit", os.path.split(expFile)[-1])
    if not os.path.exists(expFile):
        raise ExploitError("can not find exploit file '{0}'".format(expFile))

    fileName = os.path.split(expFile)[-1]
    fileName = fileName.endswith(".pyc") and fileName[:-4] or fileName.endswith(".py") and fileName[:-3] or fileName
    expModuleName = ".".join(['exploit', fileName])

    module = importlib.import_module(expModuleName)

    for member in dir(module):
        expClass = getattr(module, member)
        if inspect.isclass(expClass):
            if issubclass(expClass, Exploit) and expClass.__name__ != 'Exploit':
                break
    else:
        raise ExploitError(u"can not find exploit defination in file '{0}'".format(expFile))

    return expClass


def _execExploit(expFile, url, args):
    '''
    执行exploit
    @params:
        expFile: exploit的文件名
        args: 命令行参数
    '''

    expClass = _loadExpClass(expFile)
    
    headers = args.allHeaders if hasattr(args,'allHeaders') else {}
    exploit = expClass(url, args.cookie, headers, args.elseargs, args.proxy)
    if args.verify:
        result = exploit.execute("verify")
    elif args.attack:
        result = exploit.execute("attack")
    else:
        result = exploit.execute("verify")

    return result


@handleException
def doExploit(args, out):
    '''
    exploit模块
    '''
    out.init(u"Exploit验证系统", tofile=args.output)
    # 创建exploit信息数据库
    if args.createdb:
        try:
            ExpModel.create()
        except DBError as error:
            out.error(u"创建数据库失败，'{0}'".format(error))
        else:
            out.info(u"创建数据库成功")
        return True

    # 注册register
    if args.register:
        path = os.path.split(args.register.rstrip("\\/"))[-1]
        if ".py" in path:
            path = os.path.join(sys.path[0],"exploit",path)
        else:
            path = os.path.join(sys.path[0],path)

        if not os.path.exists(path):
            out.error(u"路径'{0}'不存在".format(path))
            return False

        if os.path.isfile(path):
            try:
                expClass = _loadExpClass(path)
            except ExploitError as error:
                out.error(u"加载'{0}'失败，'{1}'".format(path,str(error)))
                return False

            exploit = expClass()
            exploit.register()
            out.info(u"'{0}'文件中的exploit注册成功".format(path))
            return True
        else:
            files = glob.glob(os.path.join(path,"*.py"))
            for f in files:
                try:
                    expClass = _loadExpClass(f)
                    exploit = expClass()
                    exploit.register()
                except ExploitError as error:
                    continue
                else:
                    out.info(u"'{0}'文件中的exploit注册成功".format(f))
            return True

    # 更新exploit
    if args.update:
        try:
            expClass = _loadExpClass(args.update)
        except ExploitError as error:
            out.error(u"加载exploit失败，reason: {0}".format(error))
            return False
        else:
            exploit = expClass()
            exploit.update()
            out.info(u"Exploit信息更新成功")
            return True

    # 删除exploit信息条目
    if args.delete:
        expName = args.delete.strip().decode(sys.stdout.encoding).encode("utf8")
        try:
            ExpModel.delete(expName)
        except DBError as error:
            out.error(u"删除exploit信息条目失败，'{0}'".format(error))
            return False
        else:
            out.info(u"删除exploit信息条目成功")
            return True

    # 列举所有exploit
    if args.list:
        exploits = ExpModel.gets('expName','expFile')
        out.warnning(u"项目中共有以下{0}个Exploit:\n".format(len(exploits)))
        for exp in exploits:
            out.info(out.Y(u"名称 : ") + exp.expName)
            out.info(out.Y(u"文件 : ") + exp.expFile + "\n")
        return True

    # 搜索exploit
    if args.query:
        column,keyword = args.query
        exploits = ExpModel.search(column,keyword)
        if exploits:
            out.green(u"关键词 '{0}' 在 '{1}' 列中搜索结果:\n".format(keyword,column))
            for exp in exploits:
                out.info(out.Y("expName: ") + exp.expName)
                out.info(out.Y("expFile: ") + exp.expFile + "\n")
        else:
            out.red(u"在 '{0}' 列中未搜索到包含关键词 '{1}' 的exploit".format(column,keyword))
        return True
    
    # 显示某个exploit的详细信息
    if args.detail:
        expName = args.detail.strip().decode(sys.stdout.encoding).encode("utf8")
        exp = ExpModel.get(expName)
        out.info(str(exp))
        return True
        
    # Exploit执行
    if isinstance(args.execute,list):
        if not args.url:
            out.error(u"缺少 -u/--url 参数")
            return False

        if args.execute:
            for exp in args.execute:
                for url in args.url:
                    result = _execExploit(exp, url, args)
                    out.info(result)
        else:
            out.red(u"未找到指定的exploits")
            return False

        return True
    


@handleException
def doCMSIdentify(args, out):
    '''
    CMS类型识别
    '''
    out.init(u"CMS识别")

    notFoundPattern = args.notfound if args.notfound else None

    cms = CMSIdentify(args.url, notFoundPattern)
    result = cms.identify()

    if result[1]:
        out.warnning(u"\n识别成功:")
        out.info("{0} ==> ".format(args.url) + out.R(result[0]))
    else:
        out.warnning(u"识别失败")



@handleException
def doServiceIdentify(args, out):
    '''
    服务器信息识别
    '''
    out.init(u"Service识别")

    notFoundPattern = args.notfound if args.notfound else None
    cmsEnhance = args.cms if args.cms else False

    service = Service(args.url, notFoundPattern, cmsEnhance)
    result = service.identify()
    
    out.raw(result)



@handleException
def doGenPassword(args, out):
    '''
    密码生成
    '''
    out.init(u"社工密码生成", args.output)

    pwgen = PasswdGenerator(fullname=args.fullname, nickname=args.nickname, englishname=args.englishname, \
        partnername=args.partnername, birthday=args.birthday, phone=args.phone, qq=args.qq, company=args.company, \
        domain=args.domain, oldpasswd=args.oldpasswd, keywords=args.keywords, keynumbers=args.keynumbers)
    wordlist = pwgen.generate()

    out.warnning(u"生成社工密码字典如下：")
    for line in wordlist:
        out.info(line)
        out.writeLine(line)



@handleException
def doURIBrute(args, out):
    '''
    URI爆破/URI爆破字典生成
    '''
    out.init("URI资源爆破工具", args.output)

    if args.types:
        types = args.types.split(",")
        for t in types:
            if t not in URIBruter.allowTypes:
                out.error(u"不支持 '{0}' 爆破类型，请选择 {1}".format(t,",".join(URIBruter.allowTypes)))
                return False
    else:
        types = URIBruter.allowTypes

    keywords = args.keywords.split(",") if args.keywords else []
    exts = args.exts.split(",") if args.exts else []
    timeout = args.timeout if args.timeout else 10
    delay = args.delay if args.delay else 0
    size = args.size if args.size else "small"
    size = size if size in ['small','large'] else "small"

    if args.brute:
        if not args.url:
            out.error("缺少 -u/--url 参数")
            sys.exit(1)
        if args.url.startswith("@"):
            fileName = args.url[1:]
            try:
                urls = open(fileName,"r").readlines()
            except IOError as error:
                out.error(u"URL文件 '{0}' 打开失败".format(fileName))
                return False
        else:
            if not args.url.startswith("http"):
                url = "http://" + args.url.strip()
            else:
                url = args.url.strip()
            urls = [url]

        bruter = URIBruter(types=types, keywords=keywords, exts=exts, size=size)

        matchs = []
        for url in urls:
            matchs = matchs + bruter.bruteforce(url.strip(), args.notfound, args.safeurl, timeout, delay)

        if not matchs:
            out.warnning(u"未爆破到有效资源")
        else:
            out.warnning(u"爆破结果:")
            for line in matchs:
                out.info(line)
    else:
        url = args.url if args.url else None
        bruter = URIBruter(types=types, keywords=keywords, exts=exts, size=size)
        result = bruter.genDict(url)

        out.warnning(u"生成URI爆破字典如下:")
        for line in result:
            out.info(line)
            out.writeLine(line)



@handleException
def doEncode(args, out):
    '''
    字符串编码
    '''
    out.init(u"编码工具")

    code = Code(args.code)

    out.warnning(u"原始Payload：")
    out.info(args.code)
    out.warnning(u"编码结果：")
    try:
        for line in code.encode(args.type, args.method):
            out.info(line.strip())
    except EncodeError as error:
        out.error(str(error))



@handleException
def doDecode(args, out):
    '''
    字符串解码
    '''
    out.init(u"解码工具")

    code = Code(args.code)
    out.warnning(u"原始Payload：")
    out.info(args.code)
    
    try:
        if args.detect:
            out.warnning(u"编码推测结果：")
            result = code.detect()
            out.info(u"编码：" + str(result['encoding']))
            out.info(u"置信度：" + str(result['confidence']*100)[:5] + "%")
            return True

        out.warnning(u"解码结果：")
        for line in code.decode(args.type, args.method):
            out.info(line)
    except EncodeError as error:
        out.error(str(error))



@handleException
def doFileOp(args, out):
    '''
    文件处理
    '''
    out.init(u"文件处理工具")

    filePath, encodeType = args.file

    fileParser = File(filePath, encodeType)

    if args.detect:
        size = args.size if args.size else 2048
        result = fileParser.detectFileEncodeType(size)
        out.info(out.Y(u"编码：") + str(result['encoding']))
        out.info(out.Y(u"置信度：") + str(result['confidence']*100)[:5] + "%")
        return True
    if args.convertto:
        destFile, destEncodeType = args.convertto
        if not destEncodeType:
            out.error(u"\n缺少转换目的参数，使用file@encodeType指定编码类型")
            return False
        if not destFile:
            out.error(u"\n缺少目的文件，使用file@encodeType指定编码类型")
            return False
        fileParser.convert(destFile, destEncodeType)
        out.warnning(u"文件类型转换成功，目的文件为{0}".format(destFile))
        return True
    if args.hash:
        if args.hash not in File.hashMethod:
            out.error(u"hash类型'{0}'不支持，支持{1}".format(args.hash, "/".join(File.hashMethod)))
            return False
        else:
            result = fileParser.hash(args.hash)
            out.info(out.Y(u"hash类型: ") + args.hash)
            out.info(out.Y(u"结果: ") + result)
            return True
    if args.hidein:
        destFileName = "{0}_hiddenin_{1}".format(os.path.basename(filePath).split(".")[0], os.path.basename(args.hiddenin))
        destFile = os.path.join(os.path.dirname(args.hiddenin), destFileName)
        fileParser.hide(args.hiddenin, destFile)
        out.warnning(u"文件隐藏成功，目的文件为{0}".format(destFile))
        return True
    if args.list:
        out.warnning(u"文件编码转换支持的类型")
        out.info("\n".join(fileParser.convertType))
        return True
    
    enType, content = fileParser.view()
    if encodeType and enType != encodeType:
        out.warnning(u"{0}方式解码失败，使用{1}方式查看文件，内容如下：\n".format(encodeType,enType))
    else:
        out.warnning(u"{0}方式查看文件，文件内容如下：\n".format(enType))
    out.info(content)



@handleException
def doGoogleHacking(args, out):
    '''
    Google Hacking功能
    '''
    out.init(u"Google Hacking功能", args.output)

    keywords = args.keywords.decode(sys.stdin.encoding)
    engineName = args.engine.lower().strip() if args.engine else "baidu"
    size = args.size if args.size else 20

    if engineName == "baidu":
        engine = Baidu()
    elif engineName == "bing":
        engine = Bing()
    elif engineName == "google":
        engine = Google()
    else:
        out.error(u"不支持 '{0}' 搜索引擎，必须为 baidu/bing/google 之一".format(engineName))
        return False

    hostSet = set()
    out.warnning(u"'{0}' 在 '{1}' 中的搜索结果如下:\n".format(keywords, engineName))
    for item in engine.search(keywords,size):
        if not args.unique:
            out.info(out.Y("{0:>6} : ".format("title")) + item.title)
            out.info(out.Y("{0:>6} : ".format("url")) + item.url + "\n")
            out.writeLine(item.url)
        else:
            host = URL.getHost(item.url)
            if host:
                if host not in hostSet:
                    hostSet.add(host)
                    out.info(out.Y("{0:>6} : ".format("title")) + item.title)
                    out.info(out.Y("{0:>6} : ".format("url")) + item.url + "\n")
                    out.writeLine(item.url)
                else:
                    continue


def _htmlLink(target):
    return "<a href='{0}' target='_blank'>{0}</a><br/>".format("http://"+target)


@handleException
def doSubDomainScan(args, out):
    '''
    子域名爆破
    '''
    out.init("子域名爆破", tofile=args.output)
    log = Log("subdomain")
    if args.output:
        outHtml = True if args.output.endswith("html") else False
    else:
        outHtml = False

    techniques = []
    if not args.technique:
        techniques = ['z','d','g']
    else:
        if len(args.technique) <= 3:
            for t in args.technique:
                if t in "zdg":
                    techniques.append(t)
                else:
                    techniques = []
        if not techniques:
            out.error(u"不支持--techniques {0}".format(args.technique))
            return False

    dictfile = args.dict if args.dict else None
    topdomainBrute = True if args.topdomain else False
    size = args.size if args.size else 200
    if args.engine:
        if args.engine in Query.allowEngines:
            engine = args.engine
        else:
            out.error(u"不支持 --engine {0}，支持{1}".format(args.engine, str(Query.allowEngines)))
            return False
    else:
        engine = 'baidu'
    domain = URL.getHost(args.domain)

    result = set()

    dnsresolver = DnsResolver(domain)
    records = dnsresolver.getZoneRecords()
    if "z" in techniques:
        log.debug(">>>>>checking if dns zonetrans vulnerable")
        for record in records:
            log.debug("dns zonetrans vulnerable, got '{0}'".format(str(record)))
            result.add(record[0])

    if "d" in techniques:
        log.debug(">>>>>dns brutefroce")
        for item in DnsBruter(domain, dictfile, topdomainBrute):
            log.debug("dns bruteforce, got '{0}'".format(str(item)))
            result.add(item.domain)

    if "g" in techniques:
        log.debug(">>>>>google hacking")
        query = Query(site=domain) | -Query(site="www."+domain)
        for item in query.doSearch(engine=engine, size=size):
            log.debug("google hacking, got '{0}'".format(item.url))
            host = URL.getHost(item.url)
            result.add(host)

    out.warnning(u"子域名爆破结果:")
    for d in result:
        out.info(d)
        if not outHtml:
            out.writeLine(d)
        else:
            out.writeLine(d, _htmlLink)

    return True


@handleException
def doSubNetScan(args, out):
    '''
    C段扫描
    '''
    out.init(u"C段扫描", tofile=args.output)
    if args.output:
        outHtml = True if args.output.endswith("html") else False
    else:
        outHtml = False

    result = subnetScan(args.host, args.hostonly)
    if result:
        out.warnning(u"扫描结果如下:")
        for host in result:
            hostStr = ":".join([host.ip,host.port])
            out.info(hostStr)
            if not outHtml:
                out.writeLine(hostStr)
            else:
                out.writeLine(hostStr, _htmlLink)


def main():
    reload(sys)
    sys.setdefaultencoding("utf8")
    
    parser = argparse.ArgumentParser(description=u"渗透测试辅助工具")
    subparser = parser.add_subparsers(title=u"子命令", description=u"使用子命令，使用 'pen.py 子命令 -h' 获得子命令帮助")

    # cms identify
    cms = subparser.add_parser("cms", help=u"CMS 识别")
    cms.add_argument("url", help=u"指定目的URL")
    cms.add_argument("--notfound", help=u"自定义notfound页面关键字")
    cms.set_defaults(func=doCMSIdentify)

    # service identify
    service = subparser.add_parser("service", help=u"服务识别")
    service.add_argument("url", help=u"指定目的URL")
    service.add_argument("--notfound", help=u"自定义notfound页面关键字")
    service.add_argument("--cms", action="store_true", help=u"开启CMS识别加强模式")
    service.set_defaults(func=doServiceIdentify)

    # password generate
    passwdgen = subparser.add_parser("password", help=u"社会工程密码字典生成")
    passwdgen.add_argument("--fullname", help=u"指定姓名汉语拼音全拼, 例如: 'zhang san' 'lin zhi ling'")
    passwdgen.add_argument("--nickname", help=u"指定昵称")
    passwdgen.add_argument("--englishname", help=u"指定英文名，例如: 'alice' 'tom'")
    passwdgen.add_argument("--partnername", help=u"指定爱人姓名汉语拼音全拼")
    passwdgen.add_argument("--birthday", help=u"指定生日, 格式: '2000-1-10'")
    passwdgen.add_argument("--phone", help=u"指定手机号")
    passwdgen.add_argument("--qq", help=u"指定QQ号")
    passwdgen.add_argument("--company", help=u"指定公司名")
    passwdgen.add_argument("--domain", help=u"指定域名")
    passwdgen.add_argument("--oldpasswd", help=u"指定老密码")
    passwdgen.add_argument("--keywords", help=u"指定关键字列表, 例如: 'keyword1 keyword2'")
    passwdgen.add_argument("--keynumbers", help=u"指定关键数字, 例如: '123 789'")
    passwdgen.add_argument("-o","--output", help=u"指定输出文件")
    passwdgen.set_defaults(func=doGenPassword)

    # uri bruteforce
    uribrute = subparser.add_parser("uribrute", help=u"网站URI敏感资源爆破", \
        description=u"URI资源爆破，支持网站备份文件爆破、配置文件爆破、敏感目录爆破、后台爆破")
    uribrute.add_argument("-o","--output", help=u"输出字典文件")
    uribrute.add_argument("-t","--types", help=u"指定字典生成类型，以逗号分隔，支持{0}，默认使用所有类型，例如：-t webbak,cfgbak".format(str(URIBruter.allowTypes)))
    uribrute.add_argument("-k","--keywords", help=u"自定义关键字，以逗号分隔，该项仅影响生成备份文件爆破字典")
    uribrute.add_argument("-e","--exts", help=u"自定义文件后缀名，以逗号分隔，默认为php，例如：-e php,asp,aspx,jsp,html")
    uribrute.add_argument("-u", "--url", help=u"指定目的URL，如不指定则只生成字典文件")
    uribrute.add_argument("-b","--brute", action="store_true", help=u"进行URI爆破，该模式不输出字典文件")
    uribrute.add_argument("--size", help=u"指定生成字典的大小，目前只支持small和large，默认为small")
    uribrute.add_argument("--notfound", help=u"自定义notfound页面关键字")
    uribrute.add_argument("--safeurl", help=u"自定义安全URL，用于bypass安全软件")    
    uribrute.add_argument("--timeout", help=u"指定http请求超时事件, 默认为 10", type=int)
    uribrute.add_argument("--delay", help=u"指定http请求间隔时间, 默认无间隔", type=float)
    #uribrute.add_argument("--encode", help=u"指定url非ASCII编码方式, 默认为UTF-8")
    uribrute.set_defaults(func=doURIBrute)

    # exploit
    exploit = subparser.add_parser("exploit", help=u"Exploit系统", description=u"Exploit系统，执行exploit、批量执行exploit、管理exploit")
    # exploit 管理
    expManage = exploit.add_argument_group(u'exploit管理')
    expManage.add_argument("--createdb", action="store_true", help=u"创建exploit信息数据库")
    expManage.add_argument("--register", help=u"指定exploit目录或exploit文件，注册exploit信息")
    expManage.add_argument("--update", help=u"根据exploit文件更新exploit注册信息")
    expManage.add_argument("--delete", help=u"根据exploit名字删除exploit注册信息")
    expManage.add_argument("-q", "--query", action=exploitQueryParamParser, help=u"搜索exploit，参数格式column:keyword，column支持expName/os/webserver/language/appName，默认为expName")
    expManage.add_argument("-l", "--list", action="store_true", help=u"列举所有exploit")
    expManage.add_argument("--detail", help=u"根据exploit名称显示某个exploit的详细信息")
    # exploit 执行
    expExec = exploit.add_argument_group(u'exploit执行')
    expExec.add_argument("-e","--execute", action=exploitExecuteParamParser, help=u"exploit执行，参数格式column:keyword，column支持expName/os/webserver/language/appName，默认为expName")
    expExec.add_argument("-u", "--url", action=atParamParser, help=u"指定目标URL，使用@file指定url列表文件")
    expExec.add_argument("--verify", action="store_true", help=u"验证模式")
    expExec.add_argument("--attack", action="store_true", help=u"攻击模式")
    expExec.add_argument("--cookie", action=exploitCookieParamParser, help=u"指定Cookie")
    expExec.add_argument("--useragent", action=exploitUseragentParamParser, help=u"指定UserAgent")
    expExec.add_argument("--referer", action=exploitRefererParamParser, help=u"指定referer")
    expExec.add_argument("--headers", action=exploitHeadersParamParser, help=u"指定其他HTTP header,例如--header 'xxx=xxxx#yyy=yyyy'")
    expExec.add_argument("--proxy", action=exploitProxyParamParser, help=u"指定proxy，例如--proxy http:http://127.0.0.1:8888")
    expExec.add_argument("--elseargs", action=exploitElseargsParamParser, help=u"指定其他参数,例如--elseargs 'xxx=xxxx#yyy=yyyy'")
    expExec.add_argument("--output", help=u"指定输出文件，仅输出验证成功案例")
    expManage.set_defaults(func=doExploit)

    # encode
    encode = subparser.add_parser("encode", help=u"编码工具", \
        description=u"编码工具，支持的编码种类有:{0}".format(" ".join(Code.encodeTypes)))
    encode.add_argument("code", help=u"待编码字符串，建议用引号包括")
    encode.add_argument("-t", "--type", help=u"指定编码种类")
    encode.add_argument("-m", "--method", help=u"指定非ASCII字符编码方式，例如：utf8、gbk")
    encode.set_defaults(func=doEncode)

    # decode
    decode = subparser.add_parser("decode", help=u"解码工具", \
        description=u"解码工具，支持的解码种类有: {0}，其中html不能和其他编码混合".format(" ".join(Code.decodeTypes)), \
        epilog="示例:\n  pen.py decode -m utf8 target\\x3Fid\\x3D\\xC4\\xE3\\xBA\\xC3\n  pen.py decode -t decimal '116 97 114 103 101 116 63 105 100 61 196 227 186 195'", \
        formatter_class=argparse.RawDescriptionHelpFormatter)
    decode.add_argument("code", default="hello", help=u"解码字符串，例如：ASCII、URL编码，\\xaa\\xbb、0xaa0xbb、\\uxxxx\\uyyyy、混合编码")
    decode.add_argument("-t", "--type", help=u"指定解码种类，建议用引号包括")
    decode.add_argument("-m", "--method", help=u"指定非ASCII字符解码方式，例如：utf8、gbk")
    decode.add_argument("-d", "--detect", action="store_true", help=u"非ASCII编码推断")
    decode.set_defaults(func=doDecode)

    # file操作
    fileop = subparser.add_parser("file", help=u"文件处理工具", \
        description=u"文件处理工具，支持文件编码转换、文件编码类型检测、文件hash计算、文件隐藏，不支持超大文件的处理")
    fileop.add_argument("file", action=fileopFileParamParser, help=u"指定待处理文件，格式：file@encodeType")
    fileop.add_argument("-d", "--detect", action="store_true", help=u"检测文件编码类型")
    fileop.add_argument("--size", type=int, help=u"指定文件编码检测检测长度，默认为2048字节")
    fileop.add_argument("-c", "--convertto", action=fileopFileParamParser, help=u"文件编码转换，格式: file@encodeType")
    fileop.add_argument("--hash", help=u"文件hash计算，支持{0}".format("/".join(File.hashMethod)))
    fileop.add_argument("--hidein", help=u"文件隐藏，指定隐藏数据的目的文件")
    fileop.add_argument("--list", action="store_true", help=u"显示编码转换支持的类型")
    fileop.set_defaults(func=doFileOp)

    # google hacking功能
    gh = subparser.add_parser("search", help=u"GoogleHacking工具")
    gh.add_argument("keywords", help=u"指定搜索关键字，windows下引号通过两个引号转义特殊字符")
    gh.add_argument("-e", "--engine", help=u"指定搜索引擎，目前支持baidu/bing/google，默认使用baidu")
    gh.add_argument("-s", "--size", type=int, help=u"指定搜索返回条目数，默认为200条")
    gh.add_argument("-o", "--output", help=u"指定输出文件，输出文件为URL列表")
    gh.add_argument("--unique", action="store_true", help=u"设置domain唯一")
    gh.set_defaults(func=doGoogleHacking)

    # DNS 爆破
    subdomain = subparser.add_parser("domain", help=u"子域名爆破工具")
    subdomain.add_argument("domain", help=u"指定Domain")
    subdomain.add_argument("-t", "--technique", help=u"指定子域名爆破使用的技术，支持z/d/g(域传送/DNS爆破/GoogleHacking)，例如-t zg，默认使用所有技术")
    subdomain.add_argument("--dict", help=u"手动指定DNS爆破使用的字典文件，不指定则使用内置字典")
    subdomain.add_argument("--topdomain", action="store_true", help=u"指定爆破顶级域名，默认不爆破顶级域名")
    subdomain.add_argument("--size", type=int, help=u"指定Google Hacking搜索的条目数，默认为200")
    subdomain.add_argument("--engine", help=u"指定Google Hacking使用的搜索引擎，支持baidu/bing/google，默认使用baidu")
    subdomain.add_argument("-o", "--output", help=u"指定输出文件")
    subdomain.set_defaults(func=doSubDomainScan)

    # C段扫描
    subnet = subparser.add_parser("subnet", help=u"C段扫描工具")
    subnet.add_argument("host", help=u"指定扫描目的Host")
    subnet.add_argument("--hostonly", action="store_true", help=u"仅扫描目的Host，不进行C段扫描")
    subnet.add_argument("-o", "--output", help=u"指定输出文件")
    subnet.set_defaults(func=doSubNetScan)


    args = parser.parse_args()
    args.func(args)
