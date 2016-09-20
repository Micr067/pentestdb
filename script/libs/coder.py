#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
Pentestdb, a database for penetration test.
Copyright (c) 2015 alpha1e0
========================================================
字符串编解码
'''


import os
import sys
import hashlib
import urllib
import base64
import codecs
import cgi
import HTMLParser
import binascii
import re

import thirdparty.chardet as chardet
from commons import Output



class DecodeError(Exception):
    def __init__(self, msg):
        self.msg = "DecodeError: " + msg

    def __str__(self):
        return self.msg



class EncodeError(Exception):
    def __init__(self, msg):
        self.msg = "EncodeError: " + msg
        
    def __str__(self):
        return self.msg



class FileError(Exception):
    def __init__(self, msg):
        self.msg = "FileError: " + msg
        
    def __str__(self):
        return self.msg


def _utf7EncodeAll(code):
    utf16Encoded = code.encode('utf-16-be')
    result = base64.b64encode(utf16Encoded)
    return "+" + result.rstrip("=") + "-"


class Code(object):
    '''
    编解码模块
    '''
    decodeTypes = ['auto','hex','url','unicode','decimal','base64','base32','html','php-chr','utf7']
    encodeTypes = ['url','url-all','hex','decimal','unicode','unicode-all','md5','sha','base64','base32','html','html-all','php-chr','utf7','utf7-all']

    def __init__(self, code):
        '''
        输入:
            code: 待编码、解码的数据
        '''
        self.code = code.strip()

        # 正则模式，用于匹配两个字节的字符串是否符合16进制字符串模式
        self._hexPattren = re.compile(r"^[a-fA-F0-9]{2}$")


    def _isHex(self, word):
        '''
        HEX字节判断
            判断一个字节是否是16进制字节
        '''
        match = self._hexPattren.match(word)
        
        return True if match else False


    def _autoPreDecode(self, code=None):
        '''
        auto类型解码预处理
            从原始code中识别出url编码子串、HEX编码子串、原始（ASCII）子串；
        @returns:
            [[type, token]]: token数组，数组中每个元素包含类型和token字符串，token类型为"urlcode"、"hexcode"、"raw"
        '''
        code = code if code else self.code
        if "%" in code:
            code = code.replace("+"," ")

        current = code[0]=='%' and 'urlcode' or code[0:2]=='\\x' and 'hexcode' or code[0:2]=='\\u' and 'unicode' or 'raw'
        tokens = []
        tokens.append([current, ""])
        i = 0
        while i<len(code):
            if code[i] == '%' and self._isHex(code[i+1:i+3]):
                if current == 'urlcode':
                    tokens[len(tokens)-1][1] += chr(int(code[i+1:i+3],16))
                else:
                    current = 'urlcode'
                    tokens.append([current, chr(int(code[i+1:i+3],16))])
                i += 3
            elif (code[i:i+2].lower() == '\\x' or code[i:i+2].lower() == '0x') and self._isHex(code[i+2:i+4]):
                if current == "hexcode":
                    tokens[len(tokens)-1][1] += chr(int(code[i+2:i+4],16))
                else:
                    current = 'hexcode'
                    tokens.append([current, chr(int(code[i+2:i+4],16))])
                i += 4
            else:
                if current not in ['urlcode','hexcode']:
                    tokens[len(tokens)-1][1] += code[i]
                else:
                    current = 'raw'
                    tokens.append([current, code[i:i+1]])
                i += 1

        return tokens


    def _urlPreDecode(self, code=None):
        '''
        url类型解码预处理
            从原始code中识别出url编码子串、原始（ASCII）子串；
        @returns
            [[type, token]]: token数组，数组中每个元素包含类型和token字符串，token类型为"urlcode"、"raw"
        '''
        code = code if code else self.code
        code = code.replace("+"," ")
        
        current = code[0]=='%' and 'urlcode' or 'raw'
        tokens = []
        tokens.append([current, ""])
        i = 0
        while i<len(code):
            if code[i] == '%':
                if code[i] == '%' and self._isHex(code[i+1:i+3]):
                    tokens[len(tokens)-1][1] += chr(int(code[i+1:i+3],16))
                else:
                    current = 'urlcode'
                    tokens.append([current, chr(int(code[i+1:i+3],16))])
                i += 3
            else:
                if current != 'urlcode':
                    tokens[len(tokens)-1][1] += code[i]
                else:
                    current = 'raw'
                    tokens.append([current, code[i:i+1]])
                i += 1

        return tokens


    def _hexPreDecode(self, code=None):
        '''
        HEX类型解码预处理
            从原始code中识别出HEX编码子串、原始（ASCII）子串；
        @returns
            [[type, token]]: token数组，数组中每个元素包含类型和token字符串，token类型为"hexcode"、"raw"
        '''
        code = code if code else self.code
        
        current = code[0:2]=='\\x' and 'hexcode' or 'raw'
        tokens = []
        tokens.append([current, ""])
        i = 0
        while i<len(code):
            if (code[i:i+2].lower() == '\\x' or code[i:i+2].lower() == '0x') and self._isHex(code[i+2:i+4]):
                if current == "hexcode":
                    tokens[len(tokens)-1][1] += chr(int(code[i+2:i+4],16))
                else:
                    current = 'hexcode'
                    tokens.append([current, chr(int(code[i+2:i+4],16))])
                i += 4
            else:
                if current != 'hexcode':
                    tokens[len(tokens)-1][1] += code[i]
                else:
                    current = 'raw'
                    tokens.append([current, code[i:i+1]])
                i += 1

        return tokens


    def _unicodePreDecode(self, code=None):
        '''
        unicode类型解码预处理
            从原始code中识别出unicode编码、原始（ASCII）子串；
        @returns
            [[type, token]]: token数组，数组中每个元素包含类型和token字符串，token类型为"unicode"、"raw"
        '''
        code = code if code else self.code

        current = code[0:2]=='\\u' and 'unicode' or 'raw'
        tokens = []
        tokens.append([current, ""])
        i = 0
        while i<len(code):
            if code[i:i+2].lower() == '\\u' and self._isHex(code[i+2:i+4]) and self._isHex(code[i+4:i+6]):
                if current == "unicode":
                    tokens[len(tokens)-1][1] += codecs.raw_unicode_escape_decode(code[i:i+6])[0]
                else:
                    current = 'unicode'
                    tokens.append([current, codecs.raw_unicode_escape_decode(code[i:i+6])[0]])
                i += 6
            else:
                if current != 'unicode':
                    tokens[len(tokens)-1][1] += code[i]
                else:
                    current = 'raw'
                    tokens.append([current, code[i:i+1]])
                i += 1

        return tokens


    def decode(self, dtype=None, dmethod=None):
        '''
        解码
        @params
            dtype: 解码类型，默认为auto，支持URL/base64/md5/hex/unicode等类型
            dmethod: 非ASCII字符串解码类型，默认为STDOUT的编码类型，支持utf8/utf16/gbk/gb2312/big5等类型
        '''
        dtype = dtype.lower() if dtype else 'auto'
        dmethod = dmethod.lower() if dmethod else sys.stdout.encoding

        if dtype == 'decimal':
            if "," in self.code:
                tmp = [chr(int(x.strip())) for x in self.code.split(",")]
            else:
                tmp = [chr(int(x)) for x in self.code.split()]
            rawstr = "".join(tmp)
            try:
                return [rawstr.decode(dmethod)]
            except UnicodeDecodeError:
                return [repr(rawstr)]
        if dtype == 'base64':
            try:
                paddingLen = 4 - len(self.code)%4
                padding = paddingLen * "="
                basestr = base64.b64decode(self.code+padding)
                return [basestr.decode(dmethod)]
            except TypeError:
                raise DecodeError("base64 decode error")
            except UnicodeDecodeError:
                return [repr(basestr)]
        if dtype == 'base32':
            try:
                basestr = base64.b32decode(self.code)
                return [basestr.decode(dmethod)]
            except TypeError:
                raise DecodeError("base32 incorrect padding")
            except UnicodeDecodeError:
                return [repr(basestr)]

        if dtype == 'unicode':
            tokens = self._unicodePreDecode()
            return ["".join([x[1] for x in tokens])]

        if dtype == 'url':
            tokens = self._urlPreDecode()
            result = []
            tokenStr = "".join([x[1] for x in tokens])
            try:
                decodedStr = tokenStr.decode(dmethod)
            except UnicodeDecodeError:
                decodedStr = repr(tokenStr)

            return [decodedStr]

        if dtype == 'hex':
            tokens = self._hexPreDecode()
            result = []
            tokenStr = "".join([x[1] for x in tokens])
            try:
                decodedStr = tokenStr.decode(dmethod)
            except UnicodeDecodeError:
                decodedStr = repr(tokenStr)
            return [decodedStr]

        if dtype == 'html':
            htmpparser = HTMLParser.HTMLParser()
            return [htmpparser.unescape(self.code)]

        if dtype == 'auto':
            tokens = self._autoPreDecode(self.code)
            result = []
            tokenStr = "".join([x[1] for x in tokens])
            try:
                decodedStr = tokenStr.decode(dmethod)
            except UnicodeDecodeError:
                decodedStr = repr(tokenStr)
            return [decodedStr]

        if dtype == 'utf7':
            tokens = self._autoPreDecode(self.code)
            result = []
            tokenStr = "".join([x[1] for x in tokens])
            try:
                decodedStr = tokenStr.decode('utf7')
            except UnicodeDecodeError:
                decodedStr = repr(tokenStr)
            return [decodedStr]

        if dtype == 'php-chr':
            dlist = re.findall(r"\d+", self.code)
            hlist = [chr(int(x)) for x in dlist]
            rawstr = "".join(hlist)
            try:
                return [rawstr.decode(dmethod)]
            except UnicodeDecodeError:
                return [repr(rawstr)]

        raise DecodeError("unrecognized type, should be {0}".format(self.decodeTypes))


    def detect(self):
        '''
        非ASCII字符串编码类型推断
        '''
        rawstr = "".join([x[1] for x in self._autoPreDecode()])
        return chardet.detect(rawstr)


    def _utf7EncodeAll(self, code):
        '''
        UTF7编码：
            默认情况下utf7只编码非ASCII部分，该函数强制编码所有字符包括ASCII
        '''
        utf16Encoded = code.encode('utf-16-be')
        result = base64.b64encode(utf16Encoded)

        return "+" + result.rstrip("=") + "-"


    def encode(self, etype=None, emethod=None):
        '''
        编码
        @params:
            dtype: 解码类型，默认为auto，支持URL/base64/md5/hex/unicode等类型
            dmethod: 非ASCII字符串解码类型，默认为STDOUT的编码类型，支持utf8/utf16/gbk/gb2312/big5等类型
        '''
        etype = etype.lower() if etype else "url"
        emethod = emethod.lower() if emethod else sys.stdout.encoding

        ecode = self.code.decode(sys.stdout.encoding).encode(emethod)

        if etype == 'md5':
            return [hashlib.md5(ecode).hexdigest()]
        if etype == 'sha':
            result = []
            result.append("sha1: " + hashlib.sha1(ecode).hexdigest() + "\n")
            result.append("sha224: " + hashlib.sha224(ecode).hexdigest() + "\n")
            result.append("sha256: " + hashlib.sha256(ecode).hexdigest() + "\n")
            result.append("sha384: " + hashlib.sha384(ecode).hexdigest() + "\n")
            result.append("sha512: " + hashlib.sha512(ecode).hexdigest() + "\n")
            return result
        if etype == 'base64':
            return [base64.b64encode(ecode)]
        if etype == 'base32':
            return [base64.b32encode(ecode)]
        
        if etype == 'hex':
            tmp1 = ['\\'+hex(ord(x))[1:] for x in ecode]
            tmp2 = ['0'+hex(ord(x))[1:] for x in ecode]
            return ["".join(tmp1), "".join(tmp2), ",".join(tmp2)]
        if etype == 'decimal':
            tmp = [str(ord(x)) for x in ecode]
            return [" ".join(tmp), ",".join(tmp)]

        if etype == 'unicode':
            return [codecs.raw_unicode_escape_encode(self.code.decode(sys.stdout.encoding))[0]]
        if etype == 'unicode-all':
            result = ""
            tmp = codecs.raw_unicode_escape_encode(self.code.decode(sys.stdout.encoding))[0]
            current = 'unicode' if tmp[:2] == '\\u' else "raw"
            i = 0
            while i<len(tmp):
                if tmp[i:i+2].lower() == '\\u':
                    result += tmp[i:i+6]
                    if current != "unicode":
                        current = 'unicode'
                    i += 6
                else:
                    result += "\\u00" + hex(ord(tmp[i]))[2:]
                    if current != 'raw':
                        current = 'raw'
                    i += 1
            return [result]

        if etype == 'url':
            return [urllib.quote(ecode)]
        if etype == 'url-all':
            tmp = ['%'+hex(ord(x))[2:].upper() for x in ecode]
            return ["".join(tmp)]

        if etype == 'html':
            return [cgi.escape(self.code, quote=True)]
        if etype == 'html-all':
            hexstr = ["&#"+hex(ord(x))[1:]+";" for x in self.code]
            decstr = ["&#"+str(ord(x))+";" for x in self.code]
            return ["".join(hexstr), "".join(decstr)]

        if etype == 'php-chr':
            tmp = ["chr({0})".format(ord(x)) for x in ecode]
            return [".".join(tmp)]

        if etype == 'utf7':
            return [self.code.decode(sys.stdout.encoding).encode('utf7')]

        if etype == 'utf7-all':
            return [self._utf7EncodeAll(self.code.decode(sys.stdout.encoding))]

        
        raise EncodeError("unrecognized type, should be {0}".format(self.encodeTypes))



class File(object):
    '''
    文件处理
        编码推断/编码转换/hash计算/jpg隐藏/文件查看
    '''
    hashMethod = ["md5","sha","sha1","sha224","sha256","sha384","sha512","crc32"]
    _bomList = {
        "utf-8": codecs.BOM_UTF8,
        "utf-16": codecs.BOM_UTF16,
        "utf-16le": codecs.BOM_UTF16_LE,
        "utf-16be": codecs.BOM_UTF16_BE,
        "utf-32": codecs.BOM_UTF32,
        "utf-32le": codecs.BOM_UTF32_LE,
        "utf-32be": codecs.BOM_UTF32_BE,
    }
    _MAXSIZE = 16777215 # 16M

    def __init__(self, fileName, encodeType=None):
        self._fileName = fileName
        if not os.path.exists(self._fileName):
            raise FileError("file '{0}' not exists".format(os.path.abspath(self._fileName)))

        #self._encodeType = encodeType if encodeType else self.detect()['encoding']
        self._encodeType = encodeType if encodeType != 'raw' else None


    def __eq__(self, dstFile):
        if isinstance(dstFile, File):
            return self.hash() == dstFile.hash()
        elif isinstance(dstFile, basestring):
            return self.hash() == File(dstFile).hash
        else:
            return False


    def _detectEncodeType(self, content):
        result = {}

        for key,value in self._bomList.iteritems():
            if content.startswith(value):
                result['encoding'] = key + "-bom"
                result['confidence'] = 0.80
                break
        else:
            result = chardet.detect(content)

        return result


    def detectFileEncodeType(self, size=2048):
        '''
        文件编码类型推断
        '''
        size = size if size<self._MAXSIZE else self._MAXSIZE
        with open(self._fileName,"rb") as _file:
            content = _file.read(size)
        
        return self._detectEncodeType(content)


    def hash(self, method="md5"):
        '''
        文件hash计算
        '''
        content = open(self._fileName,"rb").read(self._MAXSIZE)
        if method == "md5":
            return hashlib.md5(content).hexdigest()
        if method == "sha" or method == "sha1":
            return hashlib.sha1(content).hexdigest()
        if method == "sha224":
            return hashlib.sha224(content).hexdigest()
        if method == "sha256":
            return hashlib.sha256(content).hexdigest()
        if method == "sha384":
            return hashlib.sha384(content).hexdigest()
        if method == "sha512":
            return hashlib.sha512(content).hexdigest()
        if method == "crc32":
            return "{0:x}".format(binascii.crc32(content) & 0xffffffff)
    

    def hide(self, srcFile, dstFile):
        '''
        文件隐藏
            将一个文件追加另外一个文件后面，用于制作php jpg木马等、信息隐藏
        '''
        hideData = open(self._fileName,"rb").read(self._MAXSIZE)
        with open(srcFile, "rb") as fd:
            srcData = fd.read(self._MAXSIZE)
        with open(dstFile, "wb") as fd:
            fd.write(srcData)
            fd.write(hideData)


    @property
    def convertType(self):
        '''
        convertType属性
            返回支持的文件转化方法
        '''
        convertList = list()
        for key in self._bomList:
            convertList.append(key)
            convertList.append(key+"-bom")

        return convertList + ["gbk","gb2312","big5","..."]



    def _decodeFile(self, rawContent, encodeType):
        '''
        解码原始文件
            对原始文件进行解码，转换为python unicode格式
        @params:
            rawContent: 原始文件
            encodeType: 解码类型
        @returns
            (encodeType, content, bom): 编码类型，解码后的内容，bom码；如果无法解码则编码类型为'raw'
        '''
        enType = encodeType
        if enType in [None, "", "hex"]:
            return 'raw', rawContent, None

        if enType.endswith("-bom"):
            enType = enType.replace("-bom","")
            bom = self._bomList.get(enType,None)
            if not bom:
                return "raw", rawContent, None
            else:
                rawContent = rawContent[len(bom):]
                try:
                    content = rawContent.decode(enType)
                except UnicodeDecodeError:
                    return "raw", rawContent, None
                else:
                    return encodeType, content, bom
        else:
            try:
                content = rawContent.decode(enType)
            except UnicodeDecodeError:
                return "raw", rawContent, None
            else:
                return enType, content, None


    def convert(self, dstFile, dstType):
        '''
        文件类型转换
        @params
            dstFile: 目标文件
            dstType: 目标转换类型
        '''
        with open(self._fileName,"rb") as _file:
            rawContent = _file.read(self._MAXSIZE)

        encodeType = self._encodeType
        if not encodeType:
            size = 2048 if 2048<self._MAXSIZE else self._MAXSIZE
            encodeType = self._detectEncodeType(rawContent[:size])['encoding']

        enType, content, bom = self._decodeFile(rawContent, encodeType)
        if encodeType and enType != encodeType:
            raise FileError("file decode error using '{0}' encode type".format(encodeType))

        if dstType.endswith("-bom"):
            bomed = True
            dstType = dstType.replace("-bom","") if bomed else dstType
            dstType = "utf-16be" if dstType=="utf-16" else dstType
            dstType = "utf-32be" if dstType=="utf-32" else dstType
            bom = self._bomList.get(dstType,None)
            if not bom:
                raise FileError("file type '{0}-bom' not support".format(dstType))
        else:
            bom = ""

        try:
            dstContent = content.encode(dstType)
        except LookupError as error:
            raise FileError("encode/decode type error, '{0}'".format(str(error)))

        with open(dstFile, "wb") as fd:
            fd.write(bom + dstContent)



    def _getAsciiVirualByte(self, word):
        '''
        获取可视ASCII字符
            0x20 ~ 0x7E之间的字符是可视字符，直接返回；其余字符返回"."
        '''
        if 32 <= ord(word) <= 126:
            return word
        else:
            return "."

    def _getByteHex(self, data,i,j):
        if i*16+j >=len(data):
            return "  "
        else:
            return "{0:0>2}".format(hex(ord(data[i*16+j]))[2:])

    def _getByteReal(self, data,i,j):
        if i*16+j >=len(data):
            return " "
        else:
            return Output.B(self._getAsciiVirualByte(data[i*16+j]))


    def _hexViewContent(self, rawContent):
        '''
        十六进制方式显示文件内容
        '''
        result = ""
        loopCount = len(rawContent) / 16

        for i in range(loopCount+1):
            directive = Output.Y("{0:0>8}:  ".format(hex(i*16)[2:]))
            result = result + directive

            for j in range(16):
                result = result + self._getByteHex(rawContent,i,j) + " "

            result = result + " "
            for j in range(16):
                result = result + self._getByteReal(rawContent,i,j)

            result = result + "\n"

        return result


    def view(self, encodeType=None):
        '''
        查看文件
        @params:
            encodeType: 解码类型，可手动指定，如果不指定则自动探测
        @returns:
            返回解码后的文件内容
        '''
        encodeType = encodeType if encodeType else self._encodeType

        with open(self._fileName,"rb") as _file:
            rawContent = _file.read(self._MAXSIZE)

        if encodeType == 'hex':
            content = self._hexViewContent(rawContent)
            return encodeType, content

        if not encodeType:
            size = 2048 if 2048<self._MAXSIZE else self._MAXSIZE
            encodeType = self._detectEncodeType(rawContent[:size])['encoding']

        enType, content, bom = self._decodeFile(rawContent, encodeType)
        if enType == 'raw':
            content = self._hexViewContent(rawContent)
            return 'hex', content

        return enType, content




