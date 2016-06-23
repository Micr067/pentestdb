#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
=====================================================================
字典管理。将字典加入到数据库中去重、对重复项加权打分；从数据库导出字典文件
'''


import os
import argparse

from libs.commons import Output
from libs.commons import WordList
from libs.commons import PenError
from libs.orm import Model, DBManage
from libs.orm import StringField
from libs.orm import IntegerField



class WordListModel(Model):
    _table = "wordlist"
    _database = ""

    word = StringField(primarykey=True,notnull=True,ddl="vchar(64)",vrange="1-64")
    score = IntegerField(notnull=True,ddl="integer")



class WordListManage(object):
    def __init__(self, dbfile):
        self.dbfile = dbfile
        WordListModel._database = self.dbfile


    def dump(self, size, outFile):
        '''
        从数据库中导出字典文件
        '''
        if not os.path.exists(self.dbfile):
            raise PenError("Wordlist file '{0}' dose not exists".format(self.dbfile))

        result = WordListModel.orderby("score",desc=True).limit(int(size)).getsraw("word")

        with open(outFile, "w") as _file:
            for row in result:
                try:
                    _file.write(row['word']+"\n")
                except UnicodeEncodeError:
                    continue


    def _insertLine(self, line):
        queryResult = WordListModel.where(word=line).getsraw()
        if queryResult:
            WordListModel.where(word=line).update(score=queryResult[0]['score']+1)
        else:
            WordListModel.insert(word=line,score=1)


    def load(self, dictFile):
        '''
        导入字典文件到数据库
        '''
        if not os.path.exists(self.dbfile):
            raise PenError("Wordlist file '{0}' dose not exists".format(self.dbfile))
        for line in WordList(dictFile):
            self._insertLine(line.strip())


    def createDB(self):
        '''
        创建数据库
        '''
        WordListModel.create()



if __name__ == "__main__":
    dbparse = argparse.ArgumentParser(description=u"字典数据库处理: 字典导入到数据库，数据库导出字典")
    dbparse.add_argument("database", help=u"指定数据库文件")
    dbparse.add_argument("-d", "--dump", help=u"从数据库导出字典文件")
    dbparse.add_argument("-s", "--size", type=int, help=u"指定导出字典文件的大小")
    dbparse.add_argument("-l", "--load", help=u"将指定的字典文件导入数据库")
    dbparse.add_argument("--create", action="store_true", help=u"创建数据库")
    args = dbparse.parse_args()

    try:
        dbmanage = WordListManage(args.database)
        with Output(u"字典管理") as out:
            if args.dump:
                size = args.size if args.size else 1000
                dbmanage.dump(size, args.dump)
                out.yellow(u"生成字典文件'{0}'成功".format(args.dump))
            elif args.load:
                dbmanage.load(args.load)
                out.yellow(u"字典数据库'{0}'更新成功".format(args.database))

            if args.create:
                dbmanage.createDB()
                out.yellow(u"创建数据库'{0}'成功".format(dbmanage.dbfile))
    except PenError as error:
        Output.error(str(error))
    except Exception as error:
        Output.error(u"未知错误，{0}".format(str(error)))


