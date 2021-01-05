#!/usr/bin/python
import os
from urllib.request import urlopen
import urllib
import websocket
import sys
import time
import json
import _thread

from mksdk import MkSBasicNetworkProtocol
from mksdk import MkSTransceiver
from mksdk import MkSLocalSocketUtils

def gateway_on_message (ws, message):
	GlobGateway.OnGatewayMessageEvent(message)

def gateway_on_error (ws, error):
	GlobGateway.OnGatewayErrorEvent(error)

def gateway_on_close (ws):
	GlobGateway.OnGatewayCloseEvent()
		
def gateway_on_open (ws):
	GlobGateway.OnGatewayOpenEvent()

def WebsocketWorker():
	global GlobGateway
	GlobGateway.WS = websocket.WebSocketApp(GlobGateway.URL,
				on_message = gateway_on_message,
				on_error = gateway_on_error,
				on_close = gateway_on_close)
	GlobGateway.WS.header = GlobGateway.Header
	GlobGateway.WS.on_open = gateway_on_open
	GlobGateway.WS.run_forever()

class MkSWebsocket():
	def __init__(self):
		self.GatewayOpenCallback 	= None
		self.GatewayMessageCallback = None
		self.GatewayCloseCallback 	= None
		self.GatewayErrorCallback 	= None
		self.Header 				= None
		self.URL 					= None
		self.WS  					= None

	def SetURL(self, url):
		pass

	def OnGatewayOpenEvent(self):
		if self.GatewayOpenCallback is not None:
			self.GatewayOpenCallback()

	def OnGatewayMessageEvent(self, data):
		if self.GatewayMessageCallback is not None:
			self.GatewayMessageCallback(data)

	def OnGatewayCloseEvent(self):
		if self.GatewayCloseCallback is not None:
			self.GatewayCloseCallback()

	def OnGatewayErrorEvent(self, error):
		if self.GatewayErrorCallback is not None:
			self.GatewayErrorCallback(error)
	
	def SetURL(self, url):
		self.URL = url
	
	def SetHeader(self, header):
		self.Header = header
	
	def Start(self):
		_thread.start_new_thread(WebsocketWorker, ())
	
	def Stop(self):
		pass

	def Send(self, data):
		if self.WS is not None:
			self.WS.send(data)
		else:
			print("ERROR - Send")

# websocket.enableTrace(True)
GlobGateway = MkSWebsocket()

class Network ():
	def __init__(self, uri, wsuri):
		global GlobGateway
		self.Name 		  	= "Communication to Node.JS"
		self.ClassName 		= "MkSNetwork"
		self.BasicProtocol 	= None
		self.ServerUri 	  	= uri
		self.WSServerUri  	= wsuri
		self.UserName 	  	= ""
		self.Password 	  	= ""
		self.UserDevKey   	= ""
		self.WSConnection 	= None
		self.DeviceUUID   	= ""
		self.Type 		  	= 0
		self.State 			= "DISCONN"
		self.Logger 		= None
		self.Gateway 		= GlobGateway
		self.Transceiver	= MkSTransceiver.Manager(self.WebSocketTXCallback, self.WebSocketRXCallback)

		self.OnConnectionCallback 		= None
		self.OnDataArrivedCallback 		= None
		self.OnErrorCallback 			= None
		self.OnConnectionClosedCallback = None

		self.Gateway.GatewayMessageCallback = self.GateawayOnMessageEvent
		self.Gateway.GatewayOpenCallback 	= self.GatewayOnOpenEvent
		self.Gateway.GatewayCloseCallback 	= self.GateawayOnCloseEvent
		self.Gateway.GatewayErrorCallback 	= self.GateawayOnErrorEvent

		# RX
		self.RXHandlerMethod            = {
			"websock_new_connection":	self.WebSockNewConnection_RXHandlerMethod,
			"websock_data_arrived":		self.WebSockDataArrived_RXHandlerMethod,
			"websock_disconnected":	    self.WebSockDisconnected_RXHandlerMethod,
			"websock_error":		    self.WebSockError_RXHandlerMethod,
		}
	
	def GateawayOnMessageEvent(self, message):
		self.LogMSG("({classname})# GateawayOnMessageEvent".format(classname=self.ClassName),5)
		data = json.loads(message)
		self.Transceiver.Receive({
			"type": "websock_data_arrived",
			"data": data
		})
	
	def GatewayOnOpenEvent(self):
		self.LogMSG("({classname})# GatewayOnOpenEvent".format(classname=self.ClassName),5)
		self.State = "CONN"
		self.Transceiver.Receive({
			"type": "websock_new_connection",
			"data": {}
		})
	
	def GateawayOnCloseEvent(self):
		self.LogMSG("({classname})# GateawayOnCloseEvent".format(classname=self.ClassName),5)
		self.State = "DISCONN"
		self.Transceiver.Receive({
			"type": "websock_disconnected",
			"data": {}
		})
	
	def GateawayOnErrorEvent(self, error):
		self.LogMSG("({classname})# GateawayOnErrorEvent".format(classname=self.ClassName),5)
		self.Transceiver.Receive({
			"type": "websock_error",
			"data": error
		})
	
	''' 
		Description: 	
		Return: 		
	'''   
	def WebSockNewConnection_RXHandlerMethod(self, data):
		self.LogMSG("({classname})# [WebSockNewConnection_RXHandlerMethod]".format(classname=self.ClassName),5)
		if self.OnConnectionCallback is not None:
			self.OnConnectionCallback()

	''' 
		Description: 	
		Return: 		
	'''  		
	def WebSockDataArrived_RXHandlerMethod(self, data):
		self.LogMSG("({classname})# [WebSockDataArrived_RXHandlerMethod]".format(classname=self.ClassName),1)
		packet	= data["data"]
		# Raise event for user
		try:
			if self.OnDataArrivedCallback is not None:
				self.OnDataArrivedCallback(data)
		except Exception as e:
			self.LogException("[WebSockDataArrived_RXHandlerMethod]",e,3)

	''' 
		Description: 	
		Return: 		
	'''  	
	def WebSockDisconnected_RXHandlerMethod(self, sock):
		self.LogMSG("({classname})# [WebSockDisconnected_RXHandlerMethod]".format(classname=self.ClassName),5)
		if self.OnConnectionClosedCallback is not None:
			self.OnConnectionClosedCallback()

	''' 
		Description: 	
		Return: 		
	'''  	
	def WebSockError_RXHandlerMethod(self, error):
		self.LogMSG("({classname})# [WebSockError_RXHandlerMethod] {0}".format(error,classname=self.ClassName),3)
		if self.OnErrorCallback is not None:
			self.OnErrorCallback()

	''' 
		Description: 	
		Return: 		
	'''    
	def WebSocketTXCallback(self, item):
		try:
			self.LogMSG("({classname})# [WebSocketTXCallback]".format(classname=self.ClassName),1)
			packet = item["packet"]
			if packet != "" and packet is not None:
				pckt 	= json.loads(packet)
				src  	= self.BasicProtocol.GetSourceFromJson(pckt)
				dst  	= self.BasicProtocol.GetDestinationFromJson(pckt)
				drt 	= self.BasicProtocol.GetDirectionFromJson(pckt)
				cmd 	= self.BasicProtocol.GetCommandFromJson(pckt)
				self.LogMSG("({classname})# Node -> Gateway [{2}] {0} -> {1} ({3})".format(src,dst,drt,cmd,classname=self.ClassName),5)
				self.Gateway.Send(packet)
				#self.WSConnection.send(packet)
			else:
				self.LogMSG("({classname})# Sending packet to Gateway FAILED".format(classname=self.ClassName),3)
		except Exception as e:
			self.LogException("[WebSocketTXCallback] {0}".format(item["packet"]),e,3)

	''' 
		Description: 	
		Return: 		
	'''  	
	def WebSocketRXCallback(self, item):
		try:
			self.LogMSG("({classname})# [WebSocketRXCallback]".format(classname=self.ClassName),1)
			self.RXHandlerMethod[item["type"]](item["data"])
		except Exception as e:
			self.LogException("[WebSocketTXCallback] {0}".format(item),e,3)

	''' 
		Description: 	
		Return: 		
	''' 
	def SetLogger(self, logger):
		self.Logger = logger

	''' 
		Description: 	
		Return: 		
	''' 
	def GetNetworkState(self):
		return self.State

	''' 
		Description: 	
		Return: 		
	''' 
	def GetRequest (self, url):
		try:
			req = urlopen(url, timeout=1)
			if req != None:
				data = req.read().decode('utf-8')
			else:
				return "failed"
		except:
			return "failed"

		return data

	''' 
		Description: 	
		Return: 		
	''' 		
	def PostRequset (self, url, payload):
		try:
			data = urlopen(url, payload).read().decode('utf-8')
		except:
			return "failed"
		
		return data

	''' 
		Description: 	
		Return: 		
	''' 	
	def RegisterDevice (self, device):
		jdata = json.dumps([{"key":"" + str(self.UserDevKey) + "", "payload":{"uuid":"" + str(device.UUID) + "","type":"" + str(device.Type) + "","ostype":"" + str(device.OSType) + "","osversion":"" + str(device.OSVersion) + "","brandname":"" + str(device.BrandName) + ""}}])
		data = self.PostRequset(self.ServerUri + "device/register/", jdata)

		if ('info' in data):
			return data, True
		
		return "", False

	''' 
		Description: 	
		Return: 		
	''' 
	def RegisterDeviceToPublisher (self, publisher, subscriber):
		jdata = json.dumps([{"key":"" + str(self.UserDevKey) + "", "payload":{"publisher_uuid":"" + str(publisher) + "","listener_uuid":"" + str(subscriber) + ""}}])
		data = self.PostRequset(self.ServerUri + "register/device/node/listener", jdata)

		if ('info' in data):
			return data, True
		
		return "", False

	''' 
		Description: 	
		Return: 		
	''' 
	def NodeWebfaceSocket_Thread (self):
		try:
			self.LogMSG("({classname})# Connect Gateway ({url})...".format(url=self.WSServerUri,classname=self.ClassName),5)
			self.WSConnection.keep_running = True
			self.WSConnection.run_forever()
			self.LogMSG("({classname})# Gateway Disconnected ({url})...".format(url=self.WSServerUri,classname=self.ClassName),5)
		except Exception as e:
			self.LogMSG("({classname})# NodeWebfaceSocket_Thread (ERROR) ({0})...".format(e,classname=self.ClassName),5)

	''' 
		Description: 	
		Return: 		
	''' 
	def Disconnect(self):
		self.LogMSG("({classname})# Close WebSocket Connection ...".format(classname=self.ClassName),5)
		#self.WSConnection.keep_running = False
		self.Gateway.Stop()
		time.sleep(1)

	''' 
		Description: 	
		Return: 		
	''' 
	def AccessGateway (self, key, payload):
		# Set user key, commub=nication with applications will be based on key.
		# Key will be obtain by master on provisioning flow.
		self.UserDevKey 				= key
		self.BasicProtocol 				= MkSBasicNetworkProtocol.BasicNetworkProtocol(self.DeviceUUID)
		self.BasicProtocol.SetKey(key)

		self.Gateway.SetURL(self.WSServerUri)
		self.Gateway.SetHeader({
			'uuid':self.DeviceUUID, 
			'node_type':str(self.Type), 
			'payload':str(payload), 
			'key':key
		})
		self.Gateway.Stop()
		self.Gateway.Start()

		'''
		websocket.enableTrace(False)
		self.WSConnection 				= websocket.WebSocketApp(self.WSServerUri,
																on_message = self.WSConnection_OnMessage_Handler,
																on_error = self.WSConnection_OnError_Handler,
																on_close = self.WSConnection_OnClose_Handler)
		self.WSConnection.on_open 		= self.WSConnection_OnOpen_Handler
		self.WSConnection.header		= 	{
											'uuid':self.DeviceUUID, 
											'node_type':str(self.Type), 
											'payload':str(payload), 
											'key':key
											}
		print(self.WSConnection.header)
		#self.Disconnect()
		# print("# TODO - This _thread will be created each time when connection lost or on retry!!!")
		_thread.start_new_thread(self.NodeWebfaceSocket_Thread, ())
		'''

		return True

	''' 
		Description: 	
		Return: 		
	''' 
	def SetDeviceUUID (self, uuid):
		self.DeviceUUID = uuid

	''' 
		Description: 	
		Return: 		
	''' 
	def SetDeviceType (self, type):
		self.Type = type

	''' 
		Description: 	
		Return: 		
	''' 		
	def SetApiUrl (self, url):
		self.ServerUri = url

	''' 
		Description: 	
		Return: 		
	''' 		
	def SetWsUrl (self, url):
		self.WSServerUri = url

	''' 
		Description: 	
		Return: 		
	''' 
	def SendWebSocket(self, packet):
		if self.State == "CONN":
			return self.Transceiver.Send({"packet":packet})
		else:
			return False

	''' 
		Description: 	N/A
		Return: 		N/A
	'''	
	def LogMSG(self, message, level):
		if self.Logger is not None:
			self.Logger.Log(message, level)
		else:
			print("({classname})# [NONE LOGGER] - {0}".format(message,classname=self.ClassName))

	''' 
		Description: 	N/A
		Return: 		N/A
	'''	
	def LogException(self, message, e, level):
		if self.Logger is not None:
			exeption = "({classname})# ********** EXCEPTION **********\n----\nINFO\n----\n{0}\n-----\nERROR\n-----\n({error})\n********************************\n".format(
				message,
				classname=self.ClassName,
				error=str(e))
			self.Logger.Log(exeption, level)
		else:
			print("({classname})# ********** EXCEPTION **********\n----\nINFO\n----\n{0}\n-----\nERROR\n-----\n({error})\n********************************\n".format(
				message,
				classname=self.ClassName,
				error=str(e)))